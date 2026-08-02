import requests
import pandas

def main():
    print("Collector is running...")
    print("Requests version:", requests.__version__)
    print("Pandas version:", pandas.__version__)

if __name__ == "__main__":
    main()