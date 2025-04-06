from typing import List

import os
import subprocess
import random
import asyncio
import re
import time

__all__ = ["WindscribeManager"]

def is_windscribe_installed():
    try:
        # Attempt to run the windscribe-cli command with the --version flag
        result = subprocess.run(['windscribe-cli', '--version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # If the command succeeds, Windscribe is installed
        print("Windscribe is installed:", result.stdout.decode().strip())
        return True
    except subprocess.CalledProcessError as e:
        # If the command fails, Windscribe is not installed
        print("Windscribe is not installed. Error:", e.stderr.decode().strip())
        return False
    except FileNotFoundError:
        # If the command is not found, Windscribe is not installed
        print("Windscribe CLI is not found on this system.")
        return False

class Windscribe:
    def __init__(self, serverlist, user, password):
        """loads server list and logs into Windscribe"""
        self.servers = [line.strip() for line in open(serverlist)]
        self.login(user,password)

    def login(self, user, password):
        """logs into Windscribe using provided credentials"""
        commands = ["windscribe-cli", "login"]
        proc = subprocess.Popen(commands, universal_newlines=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        proc.stdin.write(user)
        proc.stdin.write(password)

    def locations(self):
        """prints the locations available to connect to in the shell"""
        os.system("windscribe-cli locations")

    def connect(self, server=None, rand=False):
        """connects to given server, best available server if no server given, or random server"""
        if rand:
            choice = random.choice(self.servers)
            os.system(f"windscribe-cli connect {choice}")
        elif server != None:
            os.system(f"windscribe-cli connect {server}")
        else:
            os.system("windscribe-cli connect")
    
    def disconnect(self):
        """disconnect from the current server"""
        os.system("windscribe-cli disconnect")

    def logout(self):
        """logout of windscribe"""
        os.system("windscribe-cli logout")

class WindscribeManager:
    _instance = None
    connected_states = []

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(WindscribeManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self.vpn = Windscribe('servers.txt', 'markavale', '@Linux121598')

    async def reboot(self):
        print("Rebooting Windscribe...")
        subprocess.run(['windscribe-cli', 'disconnect'], check=True)
        await self.aconnect()
        print("Windscribe has been rebooted.")

    def parse_status(self, output: bytes):
        output_str = output.decode('utf-8').strip()
        lines: List[str] = output_str.split('\n')
        status_dict: dict = {}
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                status_dict[key.strip()] = value.strip()
        return status_dict
    
    def get_status(self):
        response = subprocess.run(['windscribe-cli', 'status'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return self.parse_status(response.stdout)

    async def connect(self, max_retries=15):
        retries = 0
        while retries < max_retries:
            status = self.get_status()
            state = status.get('Connect state', status.get('*Connect state'))
            if state == "Connected":
                print("VPN is connected.")
                return
            elif re.search(r"\bConnecting\b", state):
                print("VPN is connecting. Waiting for it to complete...")
                time.sleep(5)  # Wait for a few seconds before checking again
            elif state in ["Disconnected", "Disconnecting"]:
                print(f"VPN is {state}. Attempting to connect...")
                self.vpn.connect(rand=True)
                # subprocess.run(['windscribe-cli', 'connect'], check=True)
                time.sleep(random.uniform(1, 3))
            else:
                print(f"Unexpected VPN state: {state}. Retrying...")
                return
            retries += 1
        raise Exception("Failed to establish a VPN connection after multiple attempts.")

    async def aconnect(self, max_retries=15):
        retries = 0
        while retries < max_retries:
            status = self.get_status()
            state = status.get('Connect state', status.get('*Connect state'))
            if state == "Connected":
                print("VPN is connected.")
                return
            elif re.search(r"\bConnecting\b", state):
                print("VPN is connecting. Waiting for it to complete...")
                await asyncio.sleep(5)  # Wait for a few seconds before checking again
            elif state in ["Disconnected", "Disconnecting"]:
                print(f"VPN is {state}. Attempting to connect...")
                self.vpn.connect(rand=True)
                # subprocess.run(['windscribe-cli', 'connect'], check=True)
                await asyncio.sleep(random.uniform(1, 3))
            else:
                print(f"Unexpected VPN state: {state}. Retrying...")
                return
            retries += 1
        raise Exception("Failed to establish a VPN connection after multiple attempts.")

# Windsribe version -> v2.12.