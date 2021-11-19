import math
import socket
import sys
import threading
import time
import textwrap
import os
# from pyautogui import typewrite
from crccheck.crc import Crc16

# ----- KONSTANTY -----

# universal
RECV_FROM = 1500
FORMAT = "utf-8"
TIMEOUT = 200

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

# client site
# MAX_DATA_SIZE = ETH_II_PAYLOAD - IP_HEADER_LEN - UDP_HEADER_LEN - MY_HEADER
MAX_DATA_SIZE = 1500 - 20 - 8 - 8
CLIENT_INTERVAL = 10
thread_status = True

# ----- POMOCNE VECI -----
# class na lepsiu manipulaciu datami packetu
class Mypacket:

    def __init__(self, flag, number, size, crc, data):
        self.flag = flag
        self.number = number
        self.size = size
        self.crc = crc
        self.data = data

    # custom funkcia na vytvorenie byte stringu obsahujuceho udaje o packete + data
    def __bytes__(self, flag_encode_off):
        data = self.data if flag_encode_off else self.data.encode(FORMAT)
        temp = self.flag.to_bytes(1, 'big') + self.number.to_bytes(3, 'big') + self.size.to_bytes(2, 'big') + self.crc.to_bytes(2, 'big') + data
        return temp

# ----- POMOCNE FUNKCIE -----
def packet_reconstruction(packet_as_bajty, flag_decode_off):

    flag = int.from_bytes(packet_as_bajty[0:1], 'big')
    number = int.from_bytes(packet_as_bajty[1:4], 'big')
    size = int.from_bytes(packet_as_bajty[4:6], 'big')
    crc = int.from_bytes(packet_as_bajty[6:8], 'big')

    # flad urcuje ci budu prijate bajty decodeovane alebo ostanu v podobne raw bajtov
    if flag_decode_off:
        data = packet_as_bajty[8:]
    else:
        data = packet_as_bajty[8:].decode(FORMAT)

    packet_as_obj = Mypacket(flag, number, size, crc, data)
    return packet_as_obj



# ----- SERVER SITE FUNCS -----

# funkcia sluzi ako spustitel serveru
def mode_server():

    address = "127.0.0.1"
    #address = input("IP address of server: ")
    port = int(1236)
    #port = int(input("Server port: "))
    server_addr_tuple = (address, port)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(server_addr_tuple)

    server_site(server_socket, server_addr_tuple)
    pass

# zabezpecuje 3 way hand shake na strane serveru
def server_site(server_socket, server_addr_tuple):

    while (True):

        print("1 for continue as server")
        print("2 for switching role")
        print("x for exit")
        client_input = input()

        if client_input == "x":
            return

        elif client_input == "2":
            switch_users(server_socket, server_addr_tuple)
        elif client_input == "1":

            print("Server is running..")
            try:
                # cakanie na ziadost o spojenie SYN od klienta
                data, client_addr_tuple = server_socket.recvfrom(RECV_FROM)
                data = packet_reconstruction(data, False)

                # ak prisla ziadost o spojenie SYN
                if data.flag == SYN:

                    # server posle klientovy SYN ACK
                    initialization_packet = Mypacket(SYN + ACK, 0, 0, 0, "")
                    server_socket.sendto(initialization_packet.__bytes__(False), client_addr_tuple)

                    # cakanie na potvrdenie spojenia ACK od klienta
                    data, client_addr_tuple = server_socket.recvfrom(RECV_FROM)
                    data = packet_reconstruction(data, False)

                    # ak prislo ACK tak spojenie je active
                    if data.flag == ACK:
                        print(f"Established connection with: {client_addr_tuple[0]}, port: {client_addr_tuple[1]}")
                        server_as_receiver(server_socket, client_addr_tuple)
                    else:
                        print(f"Established connection failed!")
                        return

            except OSError:
                print(f"Established connection failed, handled by exception..")
                return

        else:
            print("Server: wrong input, maybe try it again!")
        pass
    pass

def server_as_receiver(server_socket, client_addr_tuple):

    while True:
        print("Server: can receiving text message or file..")
        server_socket.settimeout(TIMEOUT)

        try:
            data, client_addr_tuple = server_socket.recvfrom(RECV_FROM)
            data = packet_reconstruction(data, False)
        except (socket.timeout, socket.gaierror, socket.error, OSError, Exception) as err:
            print("Server: ", err)
            print("Server: Connection down!")
            server_socket.close()
            return

        if data.flag == RST:
            print("An RST information has been received..\nConnection shutting down..")
            server_socket.close()
            return 0

        # keep alive
        # ak prisla keep alive poziadavka
        if data.flag == KA:
            acceptation_packet = Mypacket(ACK, 0, 0, 0, "")
            server_socket.sendto(acceptation_packet.__bytes__(False), client_addr_tuple)
            continue

        if data.flag == START:
            # na kolko packetov je to co sa prijima rozdelene
            receiving_packets_total = data.number
            print(f"Incoming data will consist of {receiving_packets_total} packets\n")

            # ak sa prijal START posle sa ACK
            confirmation_packet = Mypacket(ACK, 0, 0, 0, "")
            server_socket.sendto(confirmation_packet.__bytes__(False), client_addr_tuple)

            received_packets_count = 0
            file_flag = False
            received_packets = []
            received_packets_all = []
            while True:

                received_packets_count += 1
                if receiving_packets_total - received_packets_count >= 5:
                    modulator = 5
                else:
                    modulator = receiving_packets_total % 5

                broken_packets = False
                try:
                    # dalej sa caka na primanie FILE alebo TEXT packetov
                    data, client_addr_tuple = server_socket.recvfrom(RECV_FROM)
                    data = packet_reconstruction(data, True)

                    received_crc = data.crc
                    data.crc = 0
                    calculated_crc = Crc16.calc(data.__bytes__(True))

                    if received_crc != calculated_crc:
                        broken_packets = True

                    received_packets.append(data)

                    if received_packets_count % modulator == 0:
                        if broken_packets:
                            received_packets_count -= modulator
                            confirmation_packet = Mypacket(NACK, 0, 0, 0, "")
                            server_socket.sendto(confirmation_packet.__bytes__(False), client_addr_tuple)
                        else:
                            confirmation_packet = Mypacket(ACK, 0, 0, 0, "")
                            server_socket.sendto(confirmation_packet.__bytes__(False), client_addr_tuple)
                            received_packets_all += received_packets
                            received_packets = []

                    # ak sme prijali vsetky packety
                    if received_packets_count == receiving_packets_total:

                        received_packets_all = sorted(received_packets_all, key=lambda x: x.number, reverse=False)
                        file_name = b""
                        full_message = b""
                        for packet in received_packets_all:

                            if packet.flag == FILE:
                                file_flag = True
                                file_name += packet.data

                            if packet.flag == TEXT:
                                full_message += packet.data

                        # zapiseme obsah do suboru
                        if file_flag:
                            file_name = file_name.decode(FORMAT)
                            file = open(file_name, "ab")
                            file.write(full_message)
                        # alebo vypiseme spravu
                        else:
                            print("Message: ", full_message.decode(FORMAT))
                        break

                except (socket.timeout, socket.gaierror, socket.error, OSError, Exception) as err:
                    print("Server: ", err)
                    print("Server: Connection lost! Received data can be broken..")
                    server_socket.close()
                    return

    pass



# ----- CLIENT SITE FUNCS -----

def mode_client():

    print("Client is here")

    address = "127.0.0.1"
    # address = input("IP address of server: ")
    port = int(1236)
    # port = int(input("Port of server: "))
    server_addr_tuple = (address, port)
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # client_socket.bind(server_addr_tuple)

    while True:
        try:
            client_socket.settimeout(TIMEOUT)

            # poslanie poziadavky na spojenie SYN
            initialization_packet = Mypacket(SYN, 0, 0, 0, "")
            client_socket.sendto(initialization_packet.__bytes__(False), server_addr_tuple)

            # cakanie na SYN ACK od serveru
            data, address = client_socket.recvfrom(RECV_FROM)
            data = packet_reconstruction(data, False)

            # ak od serveru prislo potvrdenie spojenia SYN ACK
            if data.flag == SYN + ACK:

                # tak posle potvrdenie aj klient teda posle ACK
                initialization_packet = Mypacket(ACK, 0, 0, 0, "")
                client_socket.sendto(initialization_packet.__bytes__(False), server_addr_tuple)

                print("Connected to address:", server_addr_tuple)
                client_site(client_socket, server_addr_tuple)

        except (socket.timeout, socket.gaierror, socket.error, OSError, Exception) as err:
            print("Client: ", err)
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
                exit_packet = Mypacket(RST, 0, 0, 0, "")
                client_socket.sendto(exit_packet.__bytes__(False), server_addr_tuple)
                continue

            elif client_input == "1":
                client_as_sender(client_socket, server_addr_tuple, "m")
                continue
            elif client_input == "2":
                client_as_sender(client_socket, server_addr_tuple, "f")
                continue

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

# funkcia sluzi na posielanie sprav alebo suborov zo strany klienta
def client_as_sender(client_socket, server_addr_tuple, type):

    try:
        message = ""
        file_flag = False
        file_name = ""
        file_path = ""
        if type == "m":
            message = input("Enter the message: ")
            message = message.encode(FORMAT)
        elif type == "f":
            file_path = input("Enter the full file path: ")
            #typewrite('C:\Users\bitar\PycharmProjects\PKS_zadanie2\\')
            file_name = os.path.basename(file_path)

            # flag na poslanie nazvu suboru
            temp_file = open(file_path, "rb")
            message = temp_file.read()
            file_path = file_path.encode(FORMAT)
            file_name = file_name.encode(FORMAT)

        # arr_mess = textwrap.wrap(message, MAX_DATA_SIZE)
        file_path_arr = [file_name[i:i+MAX_DATA_SIZE] for i in range(0, len(file_name), MAX_DATA_SIZE)]
        arr_mess = [message[i:i+MAX_DATA_SIZE] for i in range(0, len(message), MAX_DATA_SIZE)]

        # vypocet kolko bude fragmentov
        num_of_packets_total = len(file_path_arr) + len(arr_mess)
        # poslanie spravy so START flagom
        inicialization_mess_packet = Mypacket(START, num_of_packets_total, 0, 0, "")
        client_socket.sendto(inicialization_mess_packet.__bytes__(False), server_addr_tuple)

        # prijatie odpovede na START flag
        data, address = client_socket.recvfrom(RECV_FROM)
        data = packet_reconstruction(data, False)

        # ak je START potvrdeny ACK
        if data.flag == ACK:
            temp_count = 0

            temp_all_packets_arr = file_path_arr + arr_mess
            for i in range(len(temp_all_packets_arr)):

                temp_count += 1
                if num_of_packets_total - temp_count >= 5:
                    modulator = 5
                else:
                    modulator = num_of_packets_total % 5

                if temp_count <= len(file_path_arr):
                    flag = FILE
                else:
                    flag = TEXT

                packet_for_send = Mypacket(flag, temp_count, 0, 0, temp_all_packets_arr[i])
                packet_for_send.crc = Crc16.calc(packet_for_send.__bytes__(True))

                client_socket.sendto(packet_for_send.__bytes__(True), server_addr_tuple)

                if temp_count % modulator == 0:
                    data, address = client_socket.recvfrom(RECV_FROM)
                    data = packet_reconstruction(data, False)

                    if data.flag == ACK:
                        continue
                    else:
                        i -= modulator

    except (socket.timeout, socket.gaierror, socket.error, OSError, Exception) as err:
        print("Client: ", err)
        print("Client: Connection down! Data error..")
        client_socket.close()
        return

    return

# ----- OTHERS FUNC -----
def switch_users(change_socket, address):

    while True:
        print("1 for client")
        print("2 for server")
        print("x to exit")
        user_input = input()

        if user_input == "1":
            client_site(change_socket, address)
        elif user_input == "2":
            server_site(change_socket, address)
        elif user_input == "x":
            return 
        else:
            print("Wrong input, maybe try it again!")

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
