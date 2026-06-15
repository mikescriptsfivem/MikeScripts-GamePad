"""MikeScript Gamepad — map any joystick / HOTAS to a virtual Xbox controller.

The pipeline is game-agnostic:

    physical HOTAS  ->  pygame (read raw axes/buttons/hats)
                    ->  mapping + curves (deadzone / expo / invert / sensitivity)
                    ->  ViGEmBus virtual Xbox 360 pad  ->  the game

Only the JSON profile under ``profiles/`` differs per game.
"""

__version__ = "0.1.0"
