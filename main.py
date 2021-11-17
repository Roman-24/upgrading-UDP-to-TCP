
import socket
import threading
import time

# ----- KONSTANTY -----

# universal
RECV_FROM = 1500
FORMAT = "utf-8"
TIMEOUT = 20

# flags
START = 0
SYN = 1
ACK = 2
NACK = 4
KA = 16
RST = 32
TEXT = 64
FILE = 128

# server site
KEEPALIVE_REQUEST = "k"

# client site
CLIENT_INTERVAL = 10
thread_status = True



# ----- POMOCNE VECI -----
class Mypacket:

    def __init__(self, flag, number, size, crc, data):
        self.flag = flag
        self.number = number
        self.size = size
        self.crc = crc
        self.data = data

    def __bytes__(self):
        temp = self.flag.to_bytes(1, 'big') + self.number.to_bytes(3, 'big') + self.size.to_bytes(2, 'big') + self.crc.to_bytes(2, 'big') + self.data.encode(FORMAT)
        return temp

# ----- POMOCNE FUNKCIE -----
def packet_reconstruction(packet_as_bajty):

    flag = int.from_bytes(packet_as_bajty[0:1], 'big')
    number = int.from_bytes(packet_as_bajty[1:4], 'big')
    size = int.from_bytes(packet_as_bajty[4:6], 'big')
    crc = int.from_bytes(packet_as_bajty[6:8], 'big')
    data = packet_as_bajty[8:].decode(FORMAT)

    packet_as_obj = Mypacket(flag, number, size, crc, data)
    return packet_as_obj



# ----- SERVER SITE FUNCS -----

# funkcia sluzi ako spustitel serveru
def mode_server():

    address = "127.0.0.1"
    #address = input("IP address of server: ")
    port = int(1234)
    #port = int(input("Server port: "))
    addr_tuple_server = (address, port)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(addr_tuple_server)

    server_site(server_socket, addr_tuple_server)
    pass

# zanezpecuje 3 way hand shake na strane serveru
def server_site(server_socket, addr_tuple_server):

    while (True):

        print("1 for continue as server")
        print("2 for switching role")
        print("x for exit")
        client_input = input()

        if client_input == "x":
            return

        elif client_input == "2":
            switch_users(server_socket, addr_tuple_server)
        elif client_input == "1":

            print("Server is running..")
            try:
                # cakanie na ziadost o spojenie SYN od klienta
                data, addr_tuple_client = server_socket.recvfrom(RECV_FROM)
                data = packet_reconstruction(data)

                # ak prisla ziadost o spojenie SYN
                if data.flag == SYN:

                    # server posle klientovy SYN ACK
                    initialization_packet = Mypacket(SYN + ACK, 0, 0, 0, "")
                    server_socket.sendto(initialization_packet.__bytes__(), addr_tuple_client)

                    # cakanie na potvrdenie spojenia ACK od klienta
                    data, addr_tuple_client = server_socket.recvfrom(RECV_FROM)
                    data = packet_reconstruction(data)

                    # ak prislo ACK tak spojenie je active
                    if data.flag == ACK:
                        print(f"Established connection with {addr_tuple_client[0]}, port: {addr_tuple_client[1]}")
                        server_as_receiver(server_socket, addr_tuple_client)
                    else:
                        print(f"Established connection failed")
                        return

            except OSError:
                print(f"Established connection failed")
                return

        else:
            print("Server: wrong input, maybe try it again!")
        pass
    pass

def server_as_receiver(server_socket, addr_tuple_client):

    print("Server: receiving text message or file..")
    received_packets_total = 0
    full_message = []

    while True:
        server_socket.settimeout(TIMEOUT)

        # keep alive
        while True:
            data = server_socket.recvfrom(RECV_FROM)
            data = packet_reconstruction(data)

            # ak prisla keep alive poziadavka
            if data.flag == KEEPALIVE_REQUEST:
                acceptation_packet = Mypacket(ACK, 0, 0, 0, "")
                server_socket.sendto(acceptation_packet, addr_tuple_client)
                break
            else:
                break

        try:
            data, address = server_socket.recvfrom(RECV_FROM)
            data = packet_reconstruction(data)
        except (socket.timeout, socket.gaierror, socket.error, OSError, Exception) as err:
            print(err)
            print("Server: Connection down!\nShutting down..")
            server_socket.close()
            return

        # Treba vyriesit KA

        if data.flag == RST:
            print("An RST information has been received..")
            server_socket.close()
            return 0

        if data.flag == START:
            # na kolko packetov je to co sa prijima rozdelene
            number_of_received_packets = data.number
            confirmation_packet = Mypacket(ACK, 0, 0, 0, "")

    pass



# ----- CLIENT SITE FUNCS -----

def mode_client():

    print("Client is here")

    while True:

        address = "127.0.0.1"
        #address = input("IP address of server: ")
        port = int(1234)
        #port = int(input("Client port: "))
        server_addr_tuple = (address, port)
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # bin ???

        try:
            client_socket.settimeout(TIMEOUT)

            # poslanie poziadavky na spojenie SYN
            initialization_packet = Mypacket(SYN, 0, 0, 0, "")
            client_socket.sendto(initialization_packet.__bytes__(), server_addr_tuple)

            # cakanie na SYN ACK od serveru
            data, address = client_socket.recvfrom(RECV_FROM)
            data = packet_reconstruction(data)

            # ak od serveru prislo potvrdenie spojenia SYN ACK
            if data.flag == SYN + ACK:

                # tak posle potvrdenie aj klient teda posle ACK
                initialization_packet = Mypacket(ACK, 0, 0, 0, "")
                client_socket.sendto(initialization_packet.__bytes__(), server_addr_tuple)

                print("Connected to address:", server_addr_tuple)
                client_site(client_socket, server_addr_tuple)

        except (socket.timeout, socket.gaierror, socket.error, OSError, Exception) as err:
            print(err)
            print("Connection not working!\nMaybe try it again..")
            client_socket.close()
            return
            # continue

def client_site(client_socket, server_addr_tuple):
    global thread_status
    thread = None

    while True:
        print("x for exit")
        print("1 for text message")
        print("2 for file message")
        print("3 for keep alive ON")
        print("4 for keep alive OFF")
        print("5 for switching role")
        client_input = input()

        if client_input == "x" or client_input == "1" or client_input == "2" or client_input == "5":
            if thread is not None:
                thread_status = False
                thread.join()

            if client_input == "x":
                return

            elif client_input == "1":
                client_as_sender(client_socket, server_addr_tuple, "m")
            elif client_input == "2":
                client_as_sender(client_socket, server_addr_tuple, "f")

            elif client_input == "5":
                switch_users(client_socket, server_addr_tuple)

        elif client_input == "3":
            print("Keep alive ON")
            thread_status = True
            thread = start_thread(client_socket, server_addr_tuple)

        elif client_input == "4":
            if thread is not None:
                print("Keep alive OFF")
                thread_status = False
                thread.join()

        else:
            print("Wrong input, maybe try it again!")

    pass

def client_as_sender(client_socket, server_addr_tuple, type):

    pass

# ----- OTHERS FUNC -----
def switch_users(client_socket, server_addr_tuple):

    pass

def start_thread(client_socket, server_addr_tuple):
    lock = threading.Lock()
    thread = threading.Thread(target=keep_alive, args=(client_socket, server_addr_tuple, lock))
    thread.daemon = True
    thread.start()
    return thread

def keep_alive(client_socket, server_addr_tuple, lock):

    while True:

        if not thread_status:
            return

        with lock:
            client_socket.sendto(str.encode(" "), server_addr_tuple)
            data = client_socket.recv(RECV_FROM)
            information = str(data.decode())

            if information == "":
                print("Connection is working..")
            else:
                print("Connection ended")
                break
            time.sleep(CLIENT_INTERVAL)
    pass

def main():
    print("Pycharm starting..")

    device_type = input("Pre mod server zadaj: s \nPre mod client zadaj: c \nPre koniec zadaj: x\n")

    while device_type != "x":

        if device_type == "s":
            mode_server()
        elif device_type == "c":
            mode_client()
        else:
            print("Nespravna volba")

        device_type = input("Pre mod server zadaj: s \nPre mod client zadaj: c \nPre koniec zadaj: x\n")

if __name__ == "__main__":
    main()
#end
