# Rencana uji (dijalankan PEMILIK, bukan agen)

Aturan umum: sebelum setiap gerbang, restore snapshot hk-target ke clean-baseline. Buka KONSOL VMware hk-target
(jalur darurat bila SSH terputus). Sinkron kode dari hk-dev: `TARGET=hk@<ip-target> scripts/vm-sync.sh`.
Catat hasil tiap langkah di PROGRESS.md. Satu langkah gagal = berhenti, perbaiki lewat tahap terkait, ulangi dari snapshot.

## Lapis otomatis (di hk-dev dan CI)
scripts/check.sh hijau. CI hijau di PR (lint, unit py3.10-3.13, install di 4 container).

## V1: gerbang v0.1 (hk-target mentah)
```bash
cd ~/hostkeeper && sudo ./install.sh && hostkeeper version            # OS dikenali, ada "[didukung]"
sudo ./install.sh                                                      # kedua kalinya: sukses, tanpa error (idempotent)
cat > ~/p.yml <<'EOF'
version: 1
hostname: hk-gate
timezone: Asia/Jakarta
packages: [curl, htop, tree]
EOF
hostkeeper plan -c ~/p.yml; echo "exit=$?"          # tanpa root, tabel 3 perubahan, hostname tidak berubah
sudo install -d -m 700 /etc/hostkeeper && sudo install -m 600 ~/p.yml /etc/hostkeeper/profile.yml
sudo hostkeeper plan; echo "exit=$?"                # 3 perubahan, tidak ada yang diubah
sudo hostkeeper apply --yes; echo "exit=$?"         # 0
hostnamectl --static; timedatectl show -p Timezone --value; dpkg -s tree | head -2
sudo hostkeeper apply --yes                         # "0 perubahan" (tes idempotency utama)
sudo hostkeeper verify; echo "exit=$?"              # 0
sudo hostnamectl set-hostname hk-lain
sudo hostkeeper verify; echo "exit=$?"              # 3 (drift)
sudo hostkeeper apply --yes && hostnamectl --static # kembali hk-gate
# kegagalan: paket tidak ada
sed -i 's/tree\]/tree, paket-tidak-ada-xyz]/' ~/p.yml
sudo hostkeeper plan -c ~/p.yml; echo "exit=$?"     # error jelas, bukan stack trace
# lock
sudo flock /run/hostkeeper.lock sleep 20 & sleep 1; sudo hostkeeper apply --yes; echo "exit=$?"   # 4
# bukan root
hostkeeper apply; echo "exit=$?"                    # 5
sudo tail -n 5 /var/log/hostkeeper/audit.jsonl      # JSON valid, tanpa data sensitif
ls /var/lib/hostkeeper/journal/ /var/lib/hostkeeper/backups/
sudo ./uninstall.sh; test ! -e /usr/local/bin/hostkeeper && test ! -d /usr/local/lib/hostkeeper && echo BERSIH
ls /etc/hostkeeper                                  # config tetap ada (tanpa --purge)
```
Lulus jika semua komentar hasil terpenuhi. Tag lokal: git tag v0.1.0-rc (belum push).

## V2: gerbang v0.2 (hk-target mentah; konsol VMware terbuka; DUA terminal SSH)
Siapkan di hk-dev: `ssh-keygen -t ed25519 -f ~/gate_key -N ""` dan salin isi gate_key.pub ke profil.
```yaml
version: 1
hostname: hk-gate
timezone: Asia/Jakarta
packages: [curl, htop, nftables]
admin_user: deploy
ssh_authorized_keys: ["<isi gate_key.pub>"]
ssh: {port: 22, permit_root_login: false, password_auth: false}
firewall: {allow: [22/tcp]}
unattended_upgrades: true
```
```bash
sudo hostkeeper plan                       # item risiko TINGGI tampil jelas
# TERMINAL 1: sudo hostkeeper apply        # ikuti peringatan, JANGAN tutup sesi
# TERMINAL 2 (dari hk-dev): ssh -i ~/gate_key deploy@<ip-target> 'sudo -n true || echo butuh-password'
#   lalu kembali ke terminal 1 dan ketik "ya" sebelum timer habis
ssh -o PubkeyAuthentication=no deploy@<ip-target>        # harus DITOLAK
ssh root@<ip-target>                                      # harus DITOLAK
sudo sshd -T | grep -Ei '^(passwordauthentication|permitrootlogin)'   # no, no
sudo nft list table inet hostkeeper | grep -E 'dport|policy drop'
systemctl is-enabled hostkeeper-firewall.service ; cat /etc/apt/apt.conf.d/20auto-upgrades
sudo hostkeeper apply --yes ; sudo hostkeeper verify; echo "exit=$?"   # 0 perubahan, exit 0
sudo systemctl list-timers 'hostkeeper-rollback-*' --all                 # timer sudah dibatalkan
```
Skenario kegagalan (restore snapshot sebelum tiap skenario):
- A. Timer: jalankan apply, JANGAN konfirmasi. Tunggu waktu habis. Harapan: perubahan firewall dan sshd kembali, SSH tetap bisa masuk, audit mencatat undo dengan alasan timer.
- B. Sesi putus: jalankan apply, saat diminta konfirmasi tutup jendela terminal. Harapan sama dengan A (sistem pulih sendiri).
- C. Kunci salah: ganti ssh_authorized_keys dengan kunci lain milik orang lain. Harapan: gerbang sshd gagal, 00-hostkeeper.conf tidak ada, exit 1.
- D. ufw: `sudo apt install ufw && sudo ufw --force enable`, jalankan apply. Harapan: Step firewall menolak dengan penjelasan, tidak ada tabel baru.
- E. Rollback manual: setelah apply sukses, `sudo hostkeeper rollback --list` lalu `sudo hostkeeper rollback`. Harapan: file kembali persis (bandingkan dengan backups/), Step paket dilaporkan ireversibel.
- F. Ubuntu 24.04 (VM lain, opsional): ssh.port: 2222 harus ditolak dengan penjelasan ssh.socket.
- G. Wizard: dari snapshot mentah, `sudo hostkeeper setup`, jawab semua, lalu `sudo hostkeeper plan`. Bandingkan profile.yml hasilnya dengan tulis tangan. Wizard tidak boleh apply sendiri.

## V3: gerbang v0.3 (hk-target mentah; V2 sudah diterapkan)
Receiver uji di hk-dev (menerima POST dan mencetak isi):
```bash
python3 - <<'EOF'
from http.server import BaseHTTPRequestHandler, HTTPServer
class H(BaseHTTPRequestHandler):
    def do_POST(self):
        n=int(self.headers.get('content-length',0)); print(self.rfile.read(n).decode(), flush=True)
        self.send_response(200); self.end_headers()
HTTPServer(('0.0.0.0',8080),H).serve_forever()
EOF
```
Di hk-target: salin watch.example.yml ke /etc/hostkeeper/watch.yml (mode 600), isi webhook `http://<ip-dev>:8080/hook`, format json.
```bash
sudo hostkeeper watch test-notify                    # pesan tiba di receiver
sudo hostkeeper watch run ; hostkeeper status        # semua ok, exit 0
sudo hostkeeper watch enable && systemctl list-timers | grep hostkeeper
# kondisi alert: service gagal
sudo systemd-run --unit=hk-gagal /bin/false ; sleep 2 ; sudo hostkeeper watch run    # satu alert "service gagal"
sudo hostkeeper watch run ; sudo hostkeeper watch run                                 # TIDAK ada alert baru (anti-spam)
sudo systemctl reset-failed hk-gagal ; sudo hostkeeper watch run                      # pesan "pulih"
# drift profil
sudo sed -i 's/PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config.d/00-hostkeeper.conf
sudo systemctl reload ssh ; sudo hostkeeper watch run      # alert "Step sshd tidak lagi sesuai profil"
sudo hostkeeper apply --yes ; sudo hostkeeper watch run    # pulih
# receiver mati
#   hentikan receiver di hk-dev lalu: sudo hostkeeper watch run ; echo "exit=$?"   # 0, kegagalan tercatat, tidak crash
# lock saat apply
sudo flock /run/hostkeeper.lock sleep 15 & sleep 1 ; sudo hostkeeper watch run     # siklus dilewati
sudo grep -r "<ip-dev>:8080" /var/log/hostkeeper /var/lib/hostkeeper/journal || echo "URL tidak bocor"
```
Soak 24 jam: biarkan timer berjalan. Lalu `journalctl -u hostkeeper-watch --since yesterday | grep -i error` (kosong),
`ls -lh /var/lib/hostkeeper/state.db` (kecil), `systemctl status hostkeeper-watch.timer` (aktif), tidak ada lonjakan alert.

## V-FINAL: regresi penuh dari mentah (semua versi)
1. Restore clean-baseline. Sync kode dari cabang main terbaru.
2. Jalankan berurutan: install.sh -> profil lengkap V2 -> wizard (pada snapshot lain) -> apply -> verify -> watch enable -> drift -> pulih.
3. Ulangi V1 pada snapshot bersih lain untuk memastikan fitur baru tidak merusak v0.1.
4. Ikuti README dari baris pertama di VM bersih. Setiap langkah yang tidak berjalan = perbaiki README atau kode.

## Daftar periksa siap push (tiap kali dan sebelum tag rilis)
```bash
cd ~/hostkeeper && source .venv/bin/activate
git status                                   # hanya file yang kamu harapkan
scripts/check.sh                             # hijau
git diff --stat main                         # baca setiap file, tidak ada yang tak dikenal
git grep -nEi '(BEGIN [A-Z ]*PRIVATE KEY|hooks\.slack|discord(app)?\.com/api/webhooks|api[_-]?key|password *[:=])' || echo "tidak ada rahasia"
ls -l install.sh uninstall.sh                # executable
git log --oneline main..HEAD                 # pesan commit rapi, satu tahap satu cabang
cat docs/blueprint/PROGRESS.md               # status mutakhir, tidak ada catatan Insiden terbuka
```
Push dilakukan pemilik: `ssh-add ~/.ssh/hk_github && git push -u origin <cabang> ; ssh-add -D`, buka PR, tunggu CI hijau, merge.
Rilis (CD manual): ikuti docs/RELEASING.md: tag bertanda `git tag -s v0.X.0`, push tag, buat GitHub Release dari CHANGELOG.
