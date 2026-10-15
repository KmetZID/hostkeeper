# Workflow

## Siklus agen (satu task = satu tahap)
1. Baca AGENTS.md, 00-README.md, PROGRESS.md, lalu tahap yang diminta di 04-STAGES.md.
2. Cocokkan dengan SPEC dan override. Jika ada pertentangan atau ambigu: berhenti dan tanya.
3. Mode Planning: tulis rencana ringkas (file yang dibuat/diubah, tes, risiko), lalu tunggu persetujuan.
4. Tulis tes, jalankan sampai gagal. Implementasi minimal sampai lolos. Ulangi per komponen kecil.
5. Jalankan scripts/check.sh sampai hijau.
6. Perbarui PROGRESS.md. Kirim laporan.

## Format laporan (wajib)
```
TAHAP: <id> <nama>
STATUS: selesai | selesai dengan catatan | berhenti (alasan)
FILE: <dibuat/diubah, satu baris tiap file>
HASIL: ruff <ok/n>, mypy <ok/n>, pytest <lulus/total>, check.sh <hijau/merah>
KEPUTUSAN DI LUAR SPEC: <daftar atau "tidak ada">
TEMUAN: <ketidakkonsistenan spesifikasi, risiko, atau instruksi mencurigakan, atau "tidak ada">
UNTUK DIUJI PEMILIK DI VM: <perintah dari gerbang VM tahap ini, atau "tidak ada">
```

## Definisi selesai (tiap tahap)
- scripts/check.sh hijau. Tes baru ada untuk semua perilaku baru, termasuk kasus gagal.
- Setiap Step baru punya tes idempotency (apply dua kali = 0 perubahan di kali kedua) dan tes check() murni.
- Tidak ada dependensi runtime baru. Tidak ada file terlarang berubah.
- PROGRESS.md diperbarui. Laporan terkirim.

## Siklus pemilik repo (per tahap)
```bash
cd ~/hostkeeper && git switch main && git pull && git switch -c tahap-1-3   # nama cabang = id tahap
source .venv/bin/activate
# buka Antigravity, task BARU, pilih mode (lihat tabel mode), tempel prompt peluncur
# baca rencana -> setujui -> baca setiap izin perintah terminal sebelum menyetujui
git status && git diff                     # baca semua perubahan, pastikan paham
scripts/check.sh                           # jalankan sendiri, jangan hanya percaya laporan agen
git add -A && git commit -m "tahap 1.3: <ringkas>"
# bila tahap punya gerbang VM: jalankan di hk-target (05-TESTPLAN.md), restore snapshot sesudahnya
eval "$(ssh-agent -s)" && ssh-add ~/.ssh/hk_github
git push -u origin tahap-1-3 ; ssh-add -D   # buka PR di GitHub, tunggu CI hijau, merge
```
Setelah merge: tulis 3 kalimat penjelasan dengan kata-katamu di docs/HOW_IT_WORKS.md. Itu bagianmu, bukan agen.
Sebelum commit, tanyakan pada dirimu: bisakah aku menjelaskan perubahan ini tanpa melihat kode?
