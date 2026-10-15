"""Step untuk instalasi paket APT sesuai profil."""

from __future__ import annotations

from typing import ClassVar

from hostkeeper import messages
from hostkeeper.engine.step import Change, CheckResult, Risk, Step


class PackagesStep(Step):
    """Memastikan paket-paket dalam profil sudah terpasang di sistem."""

    name: ClassVar[str] = "packages"
    risk: ClassVar[Risk] = Risk.LOW
    requires: ClassVar[tuple[str, ...]] = ()
    reversible: ClassVar[bool] = False

    def enabled(self) -> bool:
        """Aktif jika profil mendefinisikan daftar paket."""
        return len(self.profile.packages) > 0

    def _query_installed(self) -> dict[str, bool]:
        """Mengambil status instalasi tiap paket dari dpkg-query."""
        if not self.profile.packages:
            return {}
        argv = ["dpkg-query", "-W", "-f=${Package} ${Status}\\n"] + list(
            self.profile.packages
        )
        res = self.runner.run(argv, mutates=False)
        # returncode 1 untuk paket tak dikenal itu normal, parse stdout
        installed: dict[str, bool] = {pkg: False for pkg in self.profile.packages}
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(" ", 1)
            if len(parts) == 2:
                pkg_name, status = parts[0], parts[1]
                if pkg_name in installed:
                    installed[pkg_name] = status == "install ok installed"
        return installed

    def check(self) -> CheckResult:
        """Memeriksa status instalasi semua paket (read-only)."""
        installed = self._query_installed()
        missing = [pkg for pkg, ok in installed.items() if not ok]
        all_ok = len(missing) == 0
        if all_ok:
            current = ", ".join(sorted(installed.keys())) + " terpasang"
        else:
            current = "belum terpasang: " + ", ".join(sorted(missing))
        detail = messages.STEP_COMPLIANT if all_ok else ""
        return CheckResult(compliant=all_ok, current=current, detail=detail)

    def plan(self) -> list[Change]:
        """Menghasilkan daftar perubahan untuk paket yang belum terpasang."""
        installed = self._query_installed()
        changes: list[Change] = []
        for pkg, ok in installed.items():
            if not ok:
                # Validasi ketersediaan paket di apt-cache
                policy_res = self.runner.run(
                    ["apt-cache", "policy", pkg], mutates=False
                )
                if (
                    "Candidate: (none)" in policy_res.stdout
                    or not policy_res.stdout.strip()
                ):
                    raise RuntimeError(
                        messages.PACKAGE_NOT_AVAILABLE.format(package=pkg)
                    )
                changes.append(
                    Change(
                        step=self.name,
                        action="install",
                        target=f"pkg:{pkg}",
                        before=None,
                        after=pkg,
                    )
                )
        return changes

    def apply(self, changes: list[Change]) -> None:
        """Menjalankan apt-get update lalu install untuk semua paket yang perlu."""
        if not changes:
            return
        pkgs = [
            c.after
            for c in changes
            if c.action == "install" and c.after is not None
        ]
        if not pkgs:
            return

        # apt-get update sekali
        update_res = self.runner.run(
            ["apt-get", "update"],
            mutates=True,
            timeout=120.0,
        )
        if not update_res.ok:
            raise RuntimeError(
                messages.APT_UPDATE_FAILED.format(stderr=update_res.stderr.strip())
            )

        # apt-get install
        install_res = self.runner.run(
            ["apt-get", "install", "-y", "--no-install-recommends"] + pkgs,
            mutates=True,
            timeout=600.0,
        )
        if not install_res.ok:
            raise RuntimeError(
                messages.APT_INSTALL_FAILED.format(
                    pkgs=", ".join(pkgs),
                    returncode=install_res.returncode,
                    stderr=install_res.stderr.strip(),
                )
            )

    def verify(self) -> CheckResult:
        """Verifikasi semua paket terpasang dengan check() ulang."""
        return self.check()

    def undo(self, changes: list[Change]) -> None:
        """Paket tidak dihapus otomatis (berisiko). Tidak ada tindakan."""
        # reversible=False; executor melaporkan "tidak dapat dibalik otomatis"
        pass
