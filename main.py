import subprocess
import sys

def main():
    print("=== Lancement de l'ETL ===")
    subprocess.run([sys.executable, "etl.py"])
    print("\n=== Lancement du dashboard Streamlit ===")
    subprocess.run([sys.executable, "-m", "streamlit", "run", "dashboard.py"])

if __name__ == "__main__":
    main()