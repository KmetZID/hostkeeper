# hostkeeper

> Alat penyiapan (*setup*) dan pemeliharaan (*watch*) server Debian dan Ubuntu berbasis profil deklaratif YAML.

Satu host, root lokal, deterministik, tanpa daemon berat, tanpa dependensi rumit.

---

## Masalah yang Dipecahkan

Menyiapkan server Linux baru sering kali berulang dan rawan salah:
1. **Risiko Terkunci**: Mengubah konfigurasi SSH atau firewall sering kali memutus sesi admin tanpa jalan kembali.
2. **Kelebihan Kompleksitas**: Menggunakan Ansible, Chef, atau Puppet untuk satu server tunggal membutuhkan instalasi runtime besar, agent, atau setup SSH remote yang berlebihan.
3. **Konfigurasi yang Bergeser (*Drift*)**: Server yang telah disiapkan seiring waktu berubah secara manual dan tidak terpantau.

**hostkeeper** memecahkan masalah ini dengan:
- **Profil Deklaratif Tunggal**: Semua konfigurasi didefinisikan dalam `/etc/hostkeeper/profile.yml`.
- **Siklus Aman**: `plan` menampilkan perubahan sebelum dieksekusi, `apply` menerapkan secara atomik dengan journal, dan `verify` memastikan kepatuhan sistem.
- **Gerbang Anti-Terkunci & Timer Rollback**: Perubahan SSH dan firewall diverifikasi secara otomatis, didukung timer rollback systemd independen jika koneksi terputus.
- **Monitoring Berkala & Deteksi Drift**: Siklus `watch` memantau beban CPU, memori, disk, update keamanan, dan mendeteksi jika konfigurasi server menyimpang dari profil.

---

## Demo

```text
$ hostkeeper plan
hostkeeper 0.3.0 plan
Profil: /etc/hostkeeper/profile.yml (version 1)
Host  : web-01

 STATUS  STEP       PERUBAHAN                                   RISIKO
 [~]     hostname   web-old -> web-01                           rendah
 [=]     timezone   Asia/Jakarta (sudah sesuai)                 -
 [+]     packages   pasang: htop, vim (curl sudah terpasang)    rendah
 [~]     sshd       Port: 22, PasswordAuth: no                  tinggi
 [~]     firewall   izinkan: 22/tcp, 80/tcp, 443/tcp            tinggi

Ringkasan: 4 perubahan, 1 sudah sesuai, 2 berisiko tinggi.
Mode plan: tidak ada yang diubah. Jalankan `sudo hostkeeper apply` untuk menerapkan.

$ sudo hostkeeper apply
hostkeeper 0.3.0 apply (run 20261016T070000Z-a1b2)
 [!] Safety timer aktif (90s). Jangan tutup sesi ini, uji dari terminal kedua.
 [~] hostname   web-old -> web-01 ................. OK (verify lolos)
 [+] packages   htop, vim ......................... OK (verify lolos)
 [~] sshd       drop-in 00-hostkeeper.conf ........ OK (verify lolos)
 [~] firewall   inet hostkeeper ................... OK (verify lolos)
 [~] Safety timer dibatalkan.
Selesai: 4 diterapkan, 0 gagal. Jalankan `hostkeeper verify` untuk memastikan.

$ hostkeeper status
hostkeeper 0.3.0 status
Host    : web-01

METRIK SISTEM:
 STATUS  METRIK                           NILAI                    
 [OK]    cpu.load1                        0.15                     
 [OK]    mem.used_percent                 42.5 %                   
 [OK]    disk./.used_percent              38.1 %                   
 [OK]    services.failed_count            0                        
 [OK]    updates.security                 0 packages               
 [OK]    time.ntp_synchronized            True                     

KESESUAIAN PROFIL:
 STATUS  STEP            KONDISI                                 
 [OK]    hostname        web-01 (sesuai)                         
 [OK]    timezone        Asia/Jakarta (sesuai)                   
 [OK]    packages        sudah terpasang (sesuai)                
 [OK]    sshd            konfigurasi efektif (sesuai)            
 [OK]    firewall        aturan aktif (sesuai)                   

Ringkasan: Semua metrik dan profil dalam kondisi OK.
```

---

## Instalasi Tiga Baris

```bash
git clone https://github.com/KmetZID/hostkeeper.git
cd hostkeeper
sudo ./install.sh
```

Setelah instalasi, perintah `hostkeeper` siap digunakan di sistem Anda.

---

## Alur Pemakaian Cepat

1. **Buat profil konfigurasi**:
   ```bash
   sudo hostkeeper setup
   ```
   Wizard interaktif akan menanyakan hostname, zona waktu, user admin, kunci SSH, firewall, dan pembaruan otomatis, lalu menyimpannya ke `/etc/hostkeeper/profile.yml`.

2. **Lihat apa yang akan diubah**:
   ```bash
   hostkeeper plan
   ```

3. **Terapkan konfigurasi**:
   ```bash
   sudo hostkeeper apply
   ```

4. **Periksa status dan kesehatan server**:
   ```bash
   hostkeeper status
   ```

5. **Aktifkan monitoring berkala**:
   ```bash
   sudo hostkeeper watch enable
   ```

---

## Kapan Jangan Pakai hostkeeper

hostkeeper dirancang spesifik untuk satu server tunggal (*single host*). **Jangan gunakan hostkeeper bila:**

- **Memerlukan orkestrasi multi-node**: Mengelola armada puluhan atau ratusan server sekaligus dengan koordinasi terpusat (gunakan Ansible, Puppet, SaltStack, atau Terraform).
- **Sistem Operasi Non-Debian/Ubuntu**: Menggunakan distribusi Linux lain seperti RHEL/CentOS, Alpine, Arch, atau sistem operasi BSD/Windows.
- **Arsitektur Kontainer Penuh / Serverless**: Sistem yang seluruhnya dibangun di atas Kubernetes, Docker swarm, atau layanan Functions-as-a-Service tanpa server VM persisten.
- **Manajemen Kluster Terdistribusi**: Mengonfigurasi replikasi kluster basis data multi-master yang memerlukan konsensus jaringan antar-host.

---

## Ringkasan Perintah

| Perintah | Deskripsi |
|---|---|
| `hostkeeper version` | Menampilkan versi dan info lingkungan sistem |
| `hostkeeper setup` | Wizard interaktif untuk membuat profil konfigurasi |
| `hostkeeper plan [-c FILE]` | Menampilkan rencana perubahan tanpa mengubah sistem |
| `sudo hostkeeper apply [-c FILE]` | Menerapkan konfigurasi dengan konfirmasi & journal |
| `hostkeeper verify [-c FILE]` | Memeriksa kepatuhan konfigurasi sistem terhadap profil |
| `sudo hostkeeper rollback [RUN_ID]` | Membalikkan perubahan dari journal eksekusi sebelumnya |
| `hostkeeper watch run` | Menjalankan satu siklus monitoring dan evaluasi metrik |
| `sudo hostkeeper watch enable` | Mengaktifkan timer systemd untuk monitoring berkala |
| `sudo hostkeeper watch disable` | Menonaktifkan timer systemd monitoring |
| `hostkeeper watch test-notify` | Mengirim notifikasi uji coba ke webhook |
| `hostkeeper status [--json]` | Menampilkan kartu kesehatan sistem & kesesuaian profil |

---

## Lisensi

Didistribusikan di bawah lisensi MIT. Lihat [LICENSE](LICENSE) untuk informasi lebih lanjut.
