
import socket

IP_HEADER_LENGTH = 20
UDP_HEADER_LENGTH = 8
ETH_II_PAYLOAD = 1500
MAX_SIZE_ON_WIRE = ETH_II_PAYLOAD - IP_HEADER_LENGTH - UDP_HEADER_LENGTH

VELKOST_HLAVICKY_DAT = 11
MAX_DATA_SIZE = MAX_SIZE_ON_WIRE - VELKOST_HLAVICKY_DAT
MIN_DATA_SIZE = 1

KEEPALIVE_INTERVAL = 30
UKONCI = []
AKTIVNY_SERVER = False


def mod_server():

    pass

def mod_client():

    pass

def main():
    print("Pycharm starting..")

    device_type = input("Pre mod server zadaj: s \nPre mod client zadaj: c \nPre koniec zadaj: x\n")

    while device_type != "x":

        if device_type == "s":
            mod_server()
        elif device_type == "c":
            mod_client()
        else:
            print("Nespravna volba")

        device_type = input("Pre mod server zadaj: s \nPre mod client zadaj: c \nPre koniec zadaj: x\n")

if __name__ == "__main__":
    main()
#end
