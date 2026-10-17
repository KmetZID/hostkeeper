# ADR 0002: Arsitektur Monitoring Tanpa Daemon Persisten

## Status
Diterima (*Accepted*)

## Konteks
Alat pemeliharaan dan pemantauan sistem sering kali dirancang sebagai daemon yang berjalan terus-menerus di latar belakang (*long-running process*). Namun pada VPS kecil atau server dengan memori terbatas (512 MB - 1 GB RAM), daemon persisten menghabiskan alokasi memori yang berharga dan berisiko mengalami kebocoran memori (*memory leak*).

## Keputusan
`hostkeeper` tidak menyediakan proses daemon latar belakang. Sebagai gantinya, eksekusi periodik dikelola melalui unit timer systemd bawaan (`hostkeeper-watch.timer`) yang menjalankan perintah oneshot `hostkeeper watch run` setiap 5 menit.

## Konsekuensi
- **Positif**:
  - Nol penggunaan memori saat idle (*zero memory footprint*).
  - Tahan terhadap kebocoran memori jangka panjang: proses hidup selama hitungan detik, menyelesaikan tugas, lalu keluar (*clean exit*).
  - Penjadwalan, logging rotasi, dan restart diserahkan sepenuhnya ke subsistem andal `systemd` dan `journald`.
- **Negatif / Mitigasi**:
  - Terdapat sedikit overhead inisialisasi Python interpreter setiap kali timer berjalan (sekitar 0.1-0.2 detik per 5 menit). Hal ini sangat dapat diabaikan dibanding konsumsi memori konstan sebuah daemon.
