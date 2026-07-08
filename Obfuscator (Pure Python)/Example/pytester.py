# script_simple.py

def main():
    print("=== Program Python Pertamaku ===")
    
    # Meminta input dari user
    nama = input("Masukkan nama kamu: ")
    print(f"Halo, {nama}! Selamat datang di dunia Python. 👋")
    
    print("\nMari kita coba hitung-hitungan simple:")
    try:
        angka1 = float(input("Masukkan angka pertama: "))
        angka2 = float(input("Masukkan angka kedua: "))
        
        # Melakukan penjumlahan
        hasil = angka1 + angka2
        
        print(f"Hasil penjumlahan dari {angka1} + {angka2} adalah: {hasil}")
    except ValueError:
        print("Oops! Kamu harus memasukkan angka yang valid.")

    print("\n===============================")
    print("Program selesai. Sampai jumpa!")

if __name__ == "__main__":
    main()