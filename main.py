import arcade
import numpy as np
from PIL import Image
import serial
import threading
import argparse
from pubsub import pub
import sys
import time
import os

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 800

def millis():
	return int(round(time.time() * 1000))

class Spaceship(arcade.Sprite):
	def __init__(self, r, g, b, row):
		fileName = 'out/player_' + str(r) + '_' + str(g) + '_' + str(b) + '.png'
		if not os.path.isfile(fileName):
			image = Image.open('spacecraft_white.png').convert('RGBA')
			image_data = np.array(image)
			image_data[(image_data == (255,255,255,255)).all(axis = -1)] = (r,g,b,255)
			final_image = Image.fromarray(image_data, mode='RGBA')
			final_image.save(fileName, 'PNG')
		
		super().__init__(fileName, 0.1)
		self.center_x = 60
		self.center_y = 50 + row * 50
		self.angle = -90
		self.color = (r, g, b)
		
		self.row = row
		self.target_x = self.center_x
	
	def update(self):
		if self.center_x < self.target_x:
			self.velocity = [(self.target_x - self.center_x) / 10, 0]
		else:
			self.velocity = [0, 0]
		super().update()
	
	def checkWinner(self):
		if self.center_x > 860:
			print('Winner: ' + str(self.row))
			return self.row
		else:
			return -1

class UnfinityGame(arcade.Window):
	# Init, Setup & Update
	def __init__(self, width, height):
		super().__init__(width, height, fullscreen=False)
		
		arcade.set_background_color(arcade.color.AMAZON)
		
		self.shipList = None
	
	def setup(self, serialPort):
		# Drawing
		self.shipList = arcade.SpriteList()
		
		# Serial
		self.serialPort = serialPort
		self.serialBuffers = []
		
		print('Starting serial port thread', '...', end='')
		serialThread = threading.Thread(target=self.readSerialData, args=(self.serialPort,))
		serialThread.start()
		print('done')
		
		# Start
		self.initGame();
	
	def update(self, delta_time):
		# Serial
		while len(self.serialBuffers) > 3:
			self.serialBuffers.pop(0)
		if len(self.serialBuffers) > 0:
			self.processSerialData(self.serialBuffers.pop(0))
		
		# Game
		self.updateGame()
		
		# Drawing
		if len(self.winners) == 0:
			self.shipList.update()
	
	# Draw
	def drawSFLine(self, x):
		for y in range(0, SCREEN_HEIGHT, 20):
			arcade.draw_rectangle_filled(x, y + 5, 10, 10, arcade.color.WHITE)
			arcade.draw_rectangle_filled(x + 10, y + 5, 10, 10, arcade.color.BLACK)
			arcade.draw_rectangle_filled(x, y + 15, 10, 10, arcade.color.BLACK)
			arcade.draw_rectangle_filled(x + 10, y + 15, 10, 10, arcade.color.WHITE)
	
	# Game methods
	def initGame(self):
		self.gameState = 'INIT'
		
		self.playerCount = 0
		self.winners = []
		
		self.countDown = 0
		self.countDownTime = 0
		
		self.sendInit()
	
	def updateGame(self):
		if self.gameState == 'COUNTDOWN':
			if millis() - self.countDownTime > 1000:
				self.countDownTime = millis()
				self.countDown -= 1
				if self.countDown == 0:
					self.sendStart()
					self.gameState = 'NORMAL'
				print('COUNTDOWN:', self.countDown)
	
	# Ship methods
	def deleteShips(self):
		for ship in self.shipList:
			ship.kill()
		self.shipList = arcade.SpriteList()
	
	def printShips(self, rgbValues):
		for index, colors in enumerate(rgbValues):
			r = colors[0:3]
			g = colors[3:6]
			b = colors[6:9]
			print('Colors:', r, g, b)
			self.shipList.append(Spaceship(r, g, b, index))
	
	def moveShips(self, steps):
		for index, step in enumerate(steps):
			self.shipList[index].target_x += int(step) * 10
	
	# Callbacks
	def on_draw(self):
		arcade.start_render()
		
		self.drawSFLine(100)
		self.drawSFLine(900)
		
		self.shipList.draw()
		
		if self.gameState == 'WAITING':
			arcade.draw_text('Warte auf Spieler\nButton drücken zum beitreten', SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2, arcade.color.WHITE, 20, align="center", anchor_x="center", anchor_y="center")
		elif self.gameState == 'READY':
			arcade.draw_text('Spielerzahl: ' + str(self.playerCount) + '\nButton drücken zum beitreten', SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2, arcade.color.WHITE, 20, align="center", anchor_x="center", anchor_y="center")
		elif self.gameState == 'COUNTDOWN':
			arcade.draw_text(str(self.countDown) + '\nStarte Spiel mit ' + str(self.playerCount) + ' Spielern\n[BACKSPACE] drücken zum abbrechen', SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2, arcade.color.WHITE, 20, align="center", anchor_x="center", anchor_y="center")
		elif self.gameState == 'FINISHED':
			arcade.draw_text('Gewonnen: ' + str(self.winners), SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2, arcade.color.WHITE, 20, align="center", anchor_x="center", anchor_y="center")
	
	def on_key_press(self, key, key_modifiers):
		if key == arcade.key.ENTER:
			if self.gameState == 'READY':
				self.gameState = 'COUNTDOWN'
				self.countDown = 5
				self.countDownTime = millis()
				self.sendReady()
				print('COUNTDOWN:', self.countDown)
		elif key == arcade.key.BACKSPACE:
			if self.gameState == 'COUNTDOWN':
				self.gameState = 'READY'
				self.sendWait()
		elif key == arcade.key.ESCAPE:
			arcade.window_commands.close_window()
	
	def on_key_release(self, key, key_modifiers):
		pass
	
	def on_mouse_press(self, x, y, button, key_modifiers):
		pass
	
	def on_mouse_motion(self, x, y, delta_x, delta_y):
		pass
	
	def on_mouse_release(self, x, y, button, key_modifiers):
		pass
	
	# Serial
	def readSerialData(self, serialPort):
		while True:
			self.serialBuffers.append(serialPort.readline().decode('utf-8'));
	
	def processSerialData(self, serialLine):
		serialLine = serialLine.rstrip('\n')
		serialLine = serialLine.rstrip('\r')
		print('Serial got "', serialLine, '": ', sep='', end='')
		if serialLine == 'wait':
			if self.gameState != 'INIT' and self.gameState != 'WAITING':
				print('Got "wait" while not in state "INIT" or "WAITING"!')
				return
			print('waiting')
			
			if self.gameState == 'INIT':
				self.gameState = 'WAITING'
		elif serialLine.startswith('ready'):
			if self.gameState != 'WAITING' and self.gameState != 'READY' and self.gameState != 'COUNTDOWN':
				print('Got "wait" while not in state "WAITING" or "READY" or "COUNTDOWN"!')
				return
			
			rgbValues = serialLine[6:].rstrip().split(',')
			
			for value in rgbValues:
				if len(value) != 9:
					print('Invalid RGB value', value)
					return
			
			self.playerCount = len(rgbValues)
			print('Player count =', self.playerCount)
			
			if self.gameState == 'WAITING':
				self.gameState = 'READY'
			
			print('Deleting previous space ships')
			self.deleteShips()
			print('Printing space ships')
			self.printShips(rgbValues)
		elif serialLine.startswith('update'):
			if self.gameState != 'NORMAL':
				print('Got "update" while not in state "NORMAL"!')
				return
			
			steps = serialLine[7:].rstrip().split(',')
			
			if len(steps) != self.playerCount:
				print('Not enough or too many steps', '(', len(steps), '!=', self.playerCount, ')')
				return
			
			print('Moving', steps, 'steps', '...', end='')
			self.moveShips(steps)
			print('done')
			
			# Check finished
			for ship in self.shipList:
				isWinner = ship.checkWinner()
				if isWinner >= 0:
					self.winners.append(isWinner)
			
			if len(self.winners) > 0:
				self.gameState = 'FINISHED'
				self.sendEnd()
		else:
			print('UNKOWN')
	
	def sendInit(self):
		print('Sending \'init\'', '...', end="");
		self.serialPort.write('init\n'.encode('utf-8'))
		print('done');
	
	def sendReady(self):
		print('Sending \'ready\'', '...', end="");
		self.serialPort.write('ready\n'.encode('utf-8'))
		print('done');
	
	def sendWait(self):
		print('Sending \'wait\'', '...', end="");
		self.serialPort.write('wait\n'.encode('utf-8'))
		print('done');
	
	def sendStart(self):
		print('Sending \'start\'', '...', end="");
		self.serialPort.write('start\n'.encode('utf-8'))
		print('done');
	
	def sendEnd(self):
		print('Sending \'end\'', '...', end="");
		self.serialPort.write('end '.encode('utf-8'))
		for i in range(len(self.winners)):
			if i > 0:
				self.serialPort.write(','.encode('utf-8'))
			self.serialPort.write(str(self.winners[i]).encode('utf-8'))
		self.serialPort.write('\n'.encode('utf-8'))
		print('done');

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('port')
	args = parser.parse_args()
	
	serialPortName = args.port
	print('Serial port:', serialPortName)
	
	print('Opening serial port', '...', end='')
	serialPort = serial.Serial(serialPortName, 115200)
	print('done')
	
	game = UnfinityGame(SCREEN_WIDTH, SCREEN_HEIGHT)
	game.setup(serialPort)
	game.set_viewport(0, SCREEN_WIDTH, 0, SCREEN_HEIGHT)
	arcade.run()
