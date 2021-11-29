import socket
import math
import sys
import threading
import time
import os
from crc16 import *

# ----- KONSTANTY -----
RECV_FROM = 1500
FORMAT = "utf-8"
# MAX_DATA_SIZE = ETH_II_PAYLOAD - IP_HEADER_LEN - UDP_HEADER_LEN - MY_HEADER
MAX_DATA_SIZE = 1500 - 20 - 8 - 8
thread_status = True
TIMEOUT = 600
KA_INTERVAL = 15
SIZE_OF_CHUNK = 10

# flags
START = 0
SYN = 1
ACK = 2
NACK = 4
KA = 16
RST = 32
TEXT = 64
FILE = 128

# ----- POMOCNE VECI -----
# class pre lepsiu manipulaciu datami packetu
class Mypacket:

    def __init__(self, flag, number, size, crc, data):
        self.flag = flag
        self.number = number
        self.size = size
        self.crc = crc
        self.data = data

    # custom metoda na vytvorenie byte stringu obsahujuceho udaje o packete + data
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
def mode_server():
    # address = "127.0.0.1"
    address = input("IP address of server: ")
    # port = int(1236)
    port = int(input("Server port: "))
    server_addr_tuple = (address, port)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(server_addr_tuple)

    server_site(server_socket, server_addr_tuple)
    pass

# zabezpecuje 3 way hand shake na strane serveru
def server_site(server_socket, server_addr_tuple):

    while True:

        print("1 for continue as server\nx for exit")
        client_input = input()

        if client_input == "x":
            return

        elif client_input == "1":

            print("Server: running..")
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
                        print(f"Server: established connection with: {client_addr_tuple[0]}, port: {client_addr_tuple[1]}")
                        server_as_receiver(server_socket, client_addr_tuple)
                        continue
                    else:
                        print(f"Server: established connection failed!")
                        return

            except OSError:
                print(f"Server: established connection failed, handled by exception..")
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
            print("Server: a RST information has been received..\nConnection shutting down..")
            server_socket.close()
            return

        # ak prisla keep alive poziadavka
        if data.flag == KA:
            print("Server: KA received")
            acceptation_packet = Mypacket(ACK, 0, 0, 0, "")
            server_socket.sendto(acceptation_packet.__bytes__(False), client_addr_tuple)
            continue

        if data.flag == START:
            # na kolko packetov je to co sa prijima rozdelene
            receiving_packets_total = data.number
            print(f"Server: incoming data will consist of {receiving_packets_total} packets..\n")

            # ak sa prijal START posle sa ACK
            confirmation_packet = Mypacket(ACK, 0, 0, 0, "")
            server_socket.sendto(confirmation_packet.__bytes__(False), client_addr_tuple)

            received_packets_count = 0
            file_flag = False
            received_chunk_packets = []
            received_packets_all = []

            # vypocitaju sa balicky kt budu chodit
            num_of_chunks = math.trunc(receiving_packets_total / SIZE_OF_CHUNK)
            size_of_last_chunk = receiving_packets_total % SIZE_OF_CHUNK
            sizes_of_chunk_arr = [SIZE_OF_CHUNK] * num_of_chunks
            sizes_of_chunk_arr.append(size_of_last_chunk)

            i = 0
            while i != len(sizes_of_chunk_arr):

                broken_packets = False
                broken_packets_local = False
                j = 0
                while j != sizes_of_chunk_arr[i]:

                    received_packets_count += 1
                    try:
                        # dalej sa caka na primanie FILE alebo TEXT packetov
                        data, client_addr_tuple = server_socket.recvfrom(RECV_FROM)
                        data = packet_reconstruction(data, True)

                        received_crc = data.crc
                        data.crc = 0
                        calculated_crc = crc16(data.__bytes__(True))

                        if received_crc != calculated_crc:
                            broken_packets = True
                            broken_packets_local = True

                        print(f"Server: received packet num: {data.number}, chyba: {broken_packets_local} , data: {data.data}")
                        broken_packets_local = False
                        received_chunk_packets.append(data)

                        if j == sizes_of_chunk_arr[i] - 1:
                            if broken_packets:
                                received_packets_count -= sizes_of_chunk_arr[i]
                                i -= 1
                                confirmation_packet = Mypacket(NACK, 0, 0, 0, "")
                                server_socket.sendto(confirmation_packet.__bytes__(False), client_addr_tuple)
                                broken_packets = False
                                received_chunk_packets = []
                                break
                            else:
                                confirmation_packet = Mypacket(ACK, 0, 0, 0, "")
                                server_socket.sendto(confirmation_packet.__bytes__(False), client_addr_tuple)
                                received_packets_all += received_chunk_packets
                                received_chunk_packets = []

                        # ak sme prijali vsetky packety
                        if received_packets_count == receiving_packets_total:

                            received_packets_all = sorted(received_packets_all, key=lambda x: x.number, reverse=False)
                            file_path = b""
                            full_message = b""
                            for packet in received_packets_all:

                                if packet.flag == FILE:
                                    file_flag = True
                                    file_path += packet.data

                                if packet.flag == TEXT:
                                    full_message += packet.data

                            # zapiseme obsah do suboru
                            if file_flag:
                                file_path = file_path.decode(FORMAT)
                                print(f"Server: the full file name was {file_path}")
                                file_name = os.path.basename(file_path)
                                new_file_path = input("Enter the path where you want save file: ")
                                file = open(new_file_path + file_name, "ab")
                                file.write(full_message)
                                print(f"Server: file {file_name} was save in {os.getcwd()}")
                            # alebo vypiseme spravu
                            else:
                                print("Server: message: ", full_message.decode(FORMAT))
                            break

                    except (socket.timeout, socket.gaierror, socket.error, OSError, Exception) as err:
                        print("Server: ", err)
                        print("Server: Connection lost! Received data can be broken..")
                        server_socket.close()
                        return
                    j += 1
                i += 1

    pass



# ----- CLIENT SITE FUNCS -----
def mode_client():
    print("Client: active..")

    # address = "127.0.0.1"
    address = input("IP address of server: ")
    # port = int(1236)
    port = int(input("Port of server: "))
    server_addr_tuple = (address, port)
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

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

                print("Client: connected to address:", server_addr_tuple)

                # ak je nadviazené spojenie aktivuje sa KA
                client_site(client_socket, server_addr_tuple)

                user_choice = input("Do you want to continue in client activity? [a/n]")
                if user_choice == "a":
                    continue
                else:
                    return

        except (socket.timeout, socket.gaierror, socket.error, OSError, Exception) as err:
            print("Client: ", err)
            print("Client: connection not working!\nMaybe try it again..")
            client_socket.close()
            return

def client_site(client_socket, server_addr_tuple):

    global thread_status
    client_ka_thread = None

    while True:

        if client_ka_thread is None:
            client_ka_thread = call_keep_alive(client_socket, server_addr_tuple)

        print("x for exit\n1 for text message\n2 for file message")
        client_input = input()

        if client_input == "x" or client_input == "1" or client_input == "2" or client_input == "3":
            if client_ka_thread is not None:
                thread_status = False
                client_ka_thread.join()
                client_ka_thread = None

            if client_input == "x":
                exit_packet = Mypacket(RST, 0, 0, 0, "")
                print("Client: client is going down..")
                client_socket.sendto(exit_packet.__bytes__(False), server_addr_tuple)
                return

            elif client_input == "1":
                client_as_sender(client_socket, server_addr_tuple, "m")
            elif client_input == "2":
                client_as_sender(client_socket, server_addr_tuple, "f")

        else:
            print("Wrong input, maybe try it again!")

    pass

# funkcia sluzi na posielanie sprav alebo suborov zo strany klienta
def client_as_sender(client_socket, server_addr_tuple, type):

    try:
        message = ""
        file_path = ""
        max_packet_data_size = int(input(f"Enter the maximum size of fragment in interval [1-{MAX_DATA_SIZE}]: "))
        # @todo, ošetrenie intervalu ??
        if type == "m":
            message = input("Enter the message: ")
            message = message.encode(FORMAT)
        elif type == "f":
            file_path = input("Enter the full file path: ")

            # flag na poslanie nazvu suboru
            temp_file = open(file_path, "rb")
            message = temp_file.read()
            file_path = file_path.encode(FORMAT)

        file_path_arr = [file_path[i:i+max_packet_data_size] for i in range(0, len(file_path), max_packet_data_size)]
        arr_mess = [message[i:i+max_packet_data_size] for i in range(0, len(message), max_packet_data_size)]

        # vypocet kolko bude fragmentov
        temp_all_packets_arr = file_path_arr + arr_mess
        num_of_packets_total = len(temp_all_packets_arr)

        # vnesenie chyby do prenosu
        wrong_packet_flag = input("Do you want mistake in communication? [a/n]: ")
        if wrong_packet_flag == "a":
            wrong_packet_num = int(input(f"Enter num of packet with will be wrong [1-{num_of_packets_total}]: "))

        # poslanie spravy so START flagom obsahujuc pocet paketov kt bude server cakat
        inicialization_mess_packet = Mypacket(START, num_of_packets_total, 0, 0, "")
        client_socket.sendto(inicialization_mess_packet.__bytes__(False), server_addr_tuple)

        # prijatie odpovede na START flag
        data, address = client_socket.recvfrom(RECV_FROM)
        data = packet_reconstruction(data, False)

        # ak je START potvrdeny ACK
        if data.flag == ACK:
            temp_count = 0

            # vypocitaju sa balicky kt budu chodit
            num_of_chunks = math.trunc(num_of_packets_total / SIZE_OF_CHUNK)
            size_of_last_chunk = num_of_packets_total % SIZE_OF_CHUNK
            sizes_of_chunk_arr = [SIZE_OF_CHUNK] * num_of_chunks
            sizes_of_chunk_arr.append(size_of_last_chunk)

            i = 0
            while i != len(sizes_of_chunk_arr):

                j = 0
                while j != sizes_of_chunk_arr[i]:

                    temp_count += 1

                    if temp_count <= len(file_path_arr):
                        flag = FILE
                    else:
                        flag = TEXT

                    packet_for_send = Mypacket(flag, temp_count, 0, 0, temp_all_packets_arr[temp_count - 1])
                    packet_for_send.crc = crc16(packet_for_send.__bytes__(True))

                    if temp_count == wrong_packet_num and wrong_packet_flag == "a":
                        wrong_packet_flag = "n"
                        packet_for_send = make_mistake_in_packet(packet_for_send)

                    client_socket.sendto(packet_for_send.__bytes__(True), server_addr_tuple)

                    if j == sizes_of_chunk_arr[i] - 1:
                        data, address = client_socket.recvfrom(RECV_FROM)
                        data = packet_reconstruction(data, False)

                        if data.flag == NACK:
                            temp_count -= sizes_of_chunk_arr[i]
                            i -= 1
                            break
                    j += 1
                i += 1

    except (socket.timeout, socket.gaierror, socket.error, OSError, Exception) as err:
        print("Client: ", err)
        print("Client: connection down! Data error..")
        client_socket.close()
        return

    return

# ----- OTHERS FUNC -----
def make_mistake_in_packet(packet):
    packet.crc -= 1
    return packet

def call_keep_alive(client_socket, server_addr_tuple):
    global thread_status
    print("Keep alive ON")
    thread_status = True
    return start_thread(client_socket, server_addr_tuple)

def start_thread(client_socket, server_addr_tuple):
    lock = threading.Lock()
    thread = threading.Thread(target=keep_alive, args=(client_socket, server_addr_tuple, lock))
    thread.daemon = True
    thread.start()
    return thread

def keep_alive(client_socket, server_addr_tuple, lock):
    global thread_status

    while True:
        if not thread_status:
            return

        with lock:
            ka_packet = Mypacket(KA, 0, 0, 0, "")
            client_socket.sendto(ka_packet.__bytes__(False), server_addr_tuple)

            data, address = client_socket.recvfrom(RECV_FROM)
            data = packet_reconstruction(data, False)

            if data.flag == ACK:
                print("Client keep_alive: connection is working..")
            else:
                print("Client keep_alive: connection ended")
                break
            time.sleep(KA_INTERVAL)
    pass

def main():
    print("Pycharm starting..")

    device_type = ""
    while device_type != "x":
        device_type = input("For server mode: s \nFor client mode: c \nFor full exit from program: x\n")

        if device_type == "s":
            mode_server()
        elif device_type == "c":
            mode_client()
        else:
            print("Nespravna volba")

if __name__ == "__main__":
    main()
#end
