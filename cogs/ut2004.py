import discord
from discord.ext import commands
import socket
import threading
import json
import configparser
import asyncio
import random

class UT2004Cog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Load configuration from the parent directory
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')

        self.channel_id = int(self.config['Discord']['channel_id'])  # Load channel ID from config
        self.host = self.config['Server']['host']  # Load host from config
        self.port = int(self.config['Server']['port'])  # Load port from config

        self.socket_server = (self.host, self.port)  # Socket server address
        self.user_colors = {}  # Dictionary to store usernames and their assigned colors

        # Persistent socket connection
        self.conn = None
        self.socket_thread = threading.Thread(target=self.start_socket_server, daemon=True)
        self.socket_thread.start()  # Start the socket server in a separate thread

    def cog_unload(self):
        # Implement logic to properly close the socket connection if needed
        if self.conn:
            self.conn.close()

    def start_socket_server(self):
        """Start the socket server to receive messages."""
        s = socket.create_server(self.socket_server)

        while True:
            print("Waiting for a connection...")
            conn, addr = s.accept()
            print(f"Connected to {addr}")
            self.conn = conn  # Store the persistent connection

            with conn:
                while True:
                    try:
                        msg_buf = conn.recv(255)
                        if msg_buf:
                            u_msg = msg_buf.decode("utf-8").strip()
                            print(f"Received from socket: {u_msg}")

                            # Split the incoming message into individual JSON objects
                            messages = u_msg.split('\0')

                            for message in messages:
                                if message:
                                    try:
                                        message_data = json.loads(message)
                                        asyncio.run_coroutine_threadsafe(self.forward_to_discord(message_data), self.bot.loop)
                                    except json.JSONDecodeError as e:
                                        print(f"Failed to parse JSON: {e}")
                    except Exception as e:
                        print(f"Socket error: {e}")
                        break

    @commands.Cog.listener()
    async def on_message(self, message):
        """Forwards messages from Discord to the socket server."""
        if message.channel.id == self.channel_id and not message.author.bot:
            if not message.content.startswith("Discord: "):
                # Call the updated send_message_to_socket function with username and message
                await self.send_message_to_socket(message.author.name, message.content)

    async def forward_to_discord(self, message_data):
        """Forwards a chat message from the socket server to Discord."""
        if message_data.get("type") == "Say":
            username = message_data.get("sender")
            msg = message_data.get("msg")
            team_index = message_data.get("teamIndex", "-1")  # Default to -1 if not provided

            # Assign color based on the team index
            if team_index == "0":  # Team 0 (Red)
                color = discord.Color.red()
            elif team_index == "1":  # Team 1 (Blue)
                color = discord.Color.blue()
            else:  # No team or other values
                if username not in self.user_colors:
                    self.user_colors[username] = self.get_random_color()
                color = self.user_colors[username]

            # Create an embed to colorize the username
            embed = discord.Embed(description=f"**{username}:** {msg}")
            embed.color = color

            channel = self.bot.get_channel(self.channel_id)
            if channel:
                try:
                    await channel.send(embed=embed)  # Send the message to the Discord channel
                    print(f"Message sent to Discord: {username}: {msg}")
                except Exception as e:
                    print(f"Failed to send message to Discord: {e}")
            else:
                print(f"Channel with ID {self.channel_id} not found.")

    async def send_message_to_socket(self, username, message_content):
        """Sends a message to the socket server."""
        if not self.conn:
            print("No socket connection available.")
            return

        try:
            # Construct the message in the required format
            msg = '{"type":"Discord","sender":"' + username + '","msg":"' + message_content + '"}\0'

            # Send the message to the socket server using the persistent connection
            self.conn.sendall(msg.encode('utf-8'))
            print(f"Sent to socket server: {username}: {message_content}")
        except BrokenPipeError:
            print("Connection lost, attempting to reconnect...")
            self.conn = None  # Reset connection to force a reconnect next time
        except Exception as e:
            print(f"Failed to send message to socket: {e}")

    def get_random_color(self):
        """Generate a random color for usernames."""
        return discord.Color(random.randint(0x000000, 0xFFFFFF))

async def setup(bot):
    await bot.add_cog(UT2004Cog(bot))
