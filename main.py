"""
Starting Template

Once you have learned how to use classes, you can begin your program with this
template.

If Python and Arcade are installed, this example can be run from the command line with:
python -m arcade.examples.starting_template
"""
import arcade
import numpy as np
from PIL import Image
import serial
import threading
import argparse
from pubsub import pub
import sys

SCREEN_WIDTH = 1067
SCREEN_HEIGHT = 600

class Spaceship(arcade.Sprite):
    def __init__(self, r, g, b, row):
        fileName = "out/player_" + str(row) + ".png"
        image = Image.open("spacecraft_white.png").convert('RGBA')
        image_data = np.array(image)
        image_data[(image_data == (255,255,255,255)).all(axis = -1)] = (r,g,b,255)
        final_image = Image.fromarray(image_data, mode='RGBA')
        final_image.save(fileName, "PNG")

        super().__init__(fileName, 0.1)
        self.center_x = 60
        self.center_y = 50 + row * 50
        self.angle = -90

        self.row = row
        self.target_x = self.center_x
    
    def update(self):
        if self.center_x < self.target_x:
            self.velocity = [1, 0]
        else:
            self.velocity = [0, 0]
        super().update()
    
    def checkWinner(self):
        if self.center_x > 860:
            print("Winner: " + str(self.row))
            return self.row
        else:
            return False
    
    


class MyGame(arcade.Window):
    """
    Main application class.

    NOTE: Go ahead and delete the methods you don't need.
    If you do need a method, delete the 'pass' and replace it
    with your own code. Don't leave 'pass' in this program.
    """
    winner = []

    def __init__(self, width, height):
        super().__init__(width, height, fullscreen=False)
        self.firstRun = True
        

        arcade.set_background_color(arcade.color.AMAZON)

        # If you have sprite lists, you should create them here,
        # and set them to None

    def setup(self, arrayOfPlayerColors):
        # Create your sprites and sprite lists here
        self.ship_list = arcade.SpriteList()

        for index, colors in enumerate(arrayOfPlayerColors):
            r = colors[0:3]
            g = colors[3:6]
            b = colors[6:9]
            print(colors, r,g,b)
            ship = Spaceship(r,g,b, index)
            self.ship_list.append(ship)        

    def move(self, steps):
        for index, step in enumerate(steps):
            self.ship_list[index].target_x += int(step)


    def on_draw(self):
        """
        Render the screen.
        """

        # This command should happen before we start drawing. It will clear
        # the screen to the background color, and erase what we drew last frame.
        arcade.start_render()

        if self.firstRun:
            self.firstRun = False
            self.setFull()

        self.drawSFLine(100)

        self.drawSFLine(900)

        # Call draw() on all your sprite lists below
        self.ship_list.draw()

        if len(self.winner) > 0:
            arcade.draw_text("Gewonnen: " + str(self.winner), 400, 250, arcade.color.WHITE, 20)
            

    def update(self, delta_time):
        """
        All the logic to move, and the game logic goes here.
        Normally, you'll call update() on the sprite lists that
        need it.
        """
        if len(self.winner) == 0:
            self.ship_list.update()

            for ship in self.ship_list:
                isWinner = ship.checkWinner()
                if isWinner is not False:
                    self.winner.append(isWinner)
            if len(self.winner) > 0:
                pub.sendMessage('gameState.winners', winners=self.winner)

    def on_key_press(self, key, key_modifiers):
        """
        Called whenever a key on the keyboard is pressed.

        For a full list of keys, see:
        http://arcade.academy/arcade.key.html
        """
        if key == arcade.key.LEFT:
            self.ship_list[0].velocity = [1,0]
        elif key == arcade.key.ESCAPE:
            arcade.window_commands.close_window()

    def on_key_release(self, key, key_modifiers):
        """
        Called whenever the user lets off a previously pressed key.
        """
        self.ship_list[0].velocity = [0,0]

    def on_mouse_motion(self, x, y, delta_x, delta_y):
        """
        Called whenever the mouse moves.
        """
        pass

    def on_mouse_press(self, x, y, button, key_modifiers):
        """
        Called when the user presses a mouse button.
        """
        pass

    def on_mouse_release(self, x, y, button, key_modifiers):
        """
        Called when a user releases a mouse button.
        """
        pass

    def drawSFLine(self, x):
        for y in range(0, SCREEN_HEIGHT, 20):
            arcade.draw_rectangle_filled(x, y + 5, 10, 10, arcade.color.WHITE)
            arcade.draw_rectangle_filled(x + 10, y + 5, 10, 10, arcade.color.BLACK)
            arcade.draw_rectangle_filled(x, y + 15, 10, 10, arcade.color.BLACK)
            arcade.draw_rectangle_filled(x + 10, y + 15, 10, 10, arcade.color.WHITE)

    def setFull(self):
        self.set_viewport(0, SCREEN_WIDTH, 0, SCREEN_HEIGHT)



class Unfinity():
    gamestate = "setup"

    def handle_data(self, serialLine):
        print(serialLine)
        if serialLine.startswith('ready') and self.gamestate == "setup":
            print("Start")
            parts = serialLine.rstrip().split(' ')
            if len(parts) == 2:
                rgbValues = parts[1].split(',')
                if len(rgbValues) == self.players:
                    invalidData = False
                    for values in rgbValues:
                        if len(values) % 9 != 0:
                            print("Invalid RGB value", values)
                            invalidData = True
                    if not invalidData:
                        gameThread = threading.Thread(target=self.startGame, args=(rgbValues,))
                        gameThread.start()
                else:
                    print("Not enough or too many rgb values")
            else:
                print("Invalid command", serialLine)
        elif serialLine.startswith('m:'):
            print("Move")
            steps = serialLine[2:].rstrip().split(',')
            if len(steps) == self.players:
                self.game.move(steps)
            else:
                print("Not enoguh or too many steps")
            print(steps)
        else:
            print(serialLine)
            

    def readSerial(self, serialPort):
        while True:
            reading = serialPort.readline().decode()
            self.handle_data(reading)

    def startGame(self, rgbValues):
        self.game = MyGame(SCREEN_WIDTH, SCREEN_HEIGHT)

        self.game.setup(rgbValues)
        self.game.setFull()
        arcade.run()

    def sendWinners(self, winners):
        winnerString = 'end ' + ','.join(str(w) for w in winners)
        print(winnerString)
        self.serialPort.write(winnerString.encode())
        

    def main(self):
        """ Main method """
        parser = argparse.ArgumentParser()
        parser.add_argument('port')
        parser.add_argument('players', type=int)

        args = parser.parse_args()

        port = args.port
        self.players = args.players

        self.serialPort = serial.Serial(port)
        self.serialPort.write(b'init %d \n' % self.players)
        
        serialThread = threading.Thread(target=self.readSerial, args=(self.serialPort,))
        serialThread.start()

        pub.subscribe(self.sendWinners, 'gameState.winners')




if __name__ == "__main__":
    uf = Unfinity()
    uf.main()
    