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

def millis():
	return int(round(time.time() * 1000))

class Spaceship(arcade.Sprite):
	def __init__(self, pos, r, g, b, row):
		fileName = 'out/player_' + str(r) + '_' + str(g) + '_' + str(b) + '.png'
		if not os.path.isfile(fileName):
			image = Image.open('spacecraft_white.png').convert('RGBA')
			image_data = np.array(image)
			image_data[(image_data == (255,255,255,255)).all(axis = -1)] = (r,g,b,255)
			final_image = Image.fromarray(image_data, mode='RGBA')
			final_image.save(fileName, 'PNG')
		
		super().__init__(fileName, 0.2)
		self.angle = -90
		self.color = (r, g, b)
		
		self.pos = pos
		self.row = row
		self.target_x = self.center_x
	
	def update(self):
		if self.center_x < self.target_x:
			self.velocity = [(self.target_x - self.center_x) / 10, 0]
		else:
			self.velocity = [0, 0]
		super().update()

class UnfinityGame(arcade.Window):
	# Init, Setup & Update
	def __init__(self):
		super().__init__(640, 480, fullscreen=True)
		
		arcade.set_background_color(arcade.color.AMAZON)
		
		self.shipList = None
	
	def setup(self, serialPort, duration, playerPositions):
		# Drawing
		self.shipList = arcade.SpriteList()
		
		# Serial
		self.serialPort = serialPort
		self.serialBuffers = []
		
		print('Starting serial port thread', '...', end='')
		serialThread = threading.Thread(target=self.readSerialData, args=(self.serialPort,))
		serialThread.start()
		print('done')
		
		self.duration = duration
		self.playerPositions = playerPositions
		
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
	def drawSFLine(self, x, y_max):
		for y in range(0, y_max, 20):
			arcade.draw_rectangle_filled(x, y + 5, 10, 10, arcade.color.WHITE)
			arcade.draw_rectangle_filled(x + 10, y + 5, 10, 10, arcade.color.BLACK)
			arcade.draw_rectangle_filled(x, y + 15, 10, 10, arcade.color.BLACK)
			arcade.draw_rectangle_filled(x + 10, y + 15, 10, 10, arcade.color.WHITE)
	
	# Game methods
	def initGame(self):
		self.gameState = 'INIT'
		
		self.activePlayers = []
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
			pos = colors[0:3]
			r = colors[3:6]
			g = colors[6:9]
			b = colors[9:12]
			self.shipList.append(Spaceship(int(pos), r, g, b, index))
	
	def moveShips(self, steps):
		for index, step in enumerate(steps):
			self.shipList[index].target_x += int(step) * 50
	
	# Callbacks
	def on_draw(self):
		width, height = self.get_size()
		self.set_viewport(0, width, 0, height)
		
		arcade.start_render()
		
		self.drawSFLine(width * 0.1, height)
		self.drawSFLine(width * 0.975, height)
		
		if self.gameState == 'WAITING' or self.gameState == 'READY' or self.gameState == 'COUNTDOWN':
			for i in range(len(self.shipList)):
				ship = self.shipList[i]
				ship.center_x = width * 0.1 - ship.height / 2
				ship.target_x = ship.center_x
				ship.center_y = height / 2 - ((len(self.shipList) - 1) / 2 - i) * 100
				ship.target_y = ship.center_y
		
		self.shipList.draw()
		
		for i in range(len(self.shipList)):
			ship = self.shipList[i]
			arcade.draw_text(str(ship.pos + 1), ship.center_x + 50, ship.center_y, arcade.color.BLACK, 20, align="center", anchor_x="center", anchor_y="center")
		
		if self.gameState == 'WAITING':
			arcade.draw_text('Warte auf Spieler\nButton drücken zum Beitreten\n', width / 2, height / 2, arcade.color.WHITE, 50, align="center", anchor_x="center", anchor_y="center")
		elif self.gameState == 'READY':
			arcade.draw_text('Spielerzahl: ' + str(len(self.activePlayers)) + '\nButton drücken zum Beitreten\n[ENTER] drücken zum Starten', width / 2, height / 2, arcade.color.WHITE, 50, align="center", anchor_x="center", anchor_y="center")
		elif self.gameState == 'COUNTDOWN':
			arcade.draw_text(str(self.countDown), width / 2, height / 2, arcade.color.WHITE, 100, align="center", anchor_x="center", anchor_y="bottom")
			arcade.draw_text('Starte Spiel mit ' + str(len(self.activePlayers)) + ' Spielern\n[BACKSPACE] drücken zum Abbrechen', width / 2, height / 2, arcade.color.WHITE, 50, align="center", anchor_x="center", anchor_y="top")
		elif self.gameState == 'NORMAL':
			# Check finished
			for ship in self.shipList:
				if ship.center_x > width * 0.975 - ship.height / 2:
					self.winners.append(ship.row)
			
			if len(self.winners) > 0:
				self.gameState = 'FINISHED'
				self.sendEnd()
		elif self.gameState == 'FINISHED':
			winnerStr = 'Spieler '
			arcade.draw_text('Gewonnen:', width / 2, height / 2, arcade.color.WHITE, 50, align="center", anchor_x="center", anchor_y="bottom")
			for i in range(len(self.winners)):
				if i > 0:
					winnerStr += ' & '
				winnerStr += str(self.winners[i] + 1)
			arcade.draw_text(winnerStr, width / 2, height / 2, arcade.color.WHITE, 75, align="center", anchor_x="center", anchor_y="top")
	
	def on_key_press(self, key, key_modifiers):
		if key == arcade.key.ENTER:
			if self.gameState == 'READY':
				self.gameState = 'COUNTDOWN'
				self.countDown = 5
				self.countDownTime = millis()
				self.sendReady()
				print('COUNTDOWN:', self.countDown)
			elif self.gameState == 'FINISHED':
				self.deleteShips()
				self.initGame()
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
				if len(value) != 12:
					print('Invalid RGB value', value)
					return
			
			self.activePlayers = []
			for rgb in rgbValues:
				self.activePlayers.append(int(rgb[0:3]))
			
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
			
			if len(steps) != len(self.activePlayers):
				print('Not enough or too many steps', '(', len(steps), '!=', len(self.activePlayers), ')')
				return
			
			print('Moving', steps, 'steps', '...', end='')
			self.moveShips(steps)
			print('done')
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
		self.serialPort.write(('start ' + str(duration) + ' ').encode('utf-8'))
		for i in range(len(self.activePlayers)):
			if i > 0:
				self.serialPort.write(','.encode('utf-8'))
			idx = self.activePlayers[i];
			if (idx < len(self.playerPositions)):
				self.serialPort.write(str(self.playerPositions[idx]).encode('utf-8'))
			else:
				self.serialPort.write(str(0).encode('utf-8'))
		self.serialPort.write('\n'.encode('utf-8'))
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
	parser.add_argument('duration')
	parser.add_argument('positions', metavar='N', type=int, nargs='+')
	
	args = parser.parse_args()
	
	serialPortName = args.port
	print('Serial port:', serialPortName)
	duration = args.duration
	print('Duration:', duration)
	playerPositions = args.positions
	print('Player positions:', playerPositions)
	
	print('Opening serial port', '...', end='')
	serialPort = serial.Serial(serialPortName, 115200)
	print('done')
	
	game = UnfinityGame()
	game.setup(serialPort, duration, playerPositions)
	arcade.run()
