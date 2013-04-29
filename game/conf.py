import pygame as pg

from engine import conf
from engine.util import dd


class Conf (object):
    # window
    WINDOW_TITLE = 'It\'s Probably Not Even Paint'
    WINDOW_ICON = conf.IMG_DIR + 'icon.png'

    # input
    KEYS_MOVE = (
        ((pg.K_a, pg.K_q), (pg.K_w, pg.K_z, pg.K_COMMA), (pg.K_d, pg.K_e),
         (pg.K_s, pg.K_o)),
        ((pg.K_LEFT,), (pg.K_UP,), (pg.K_RIGHT,), (pg.K_DOWN,))
    )
    KEYS_FIRE = ((pg.K_SPACE,), (pg.K_RCTRL,))
    KEYS_RUN = ((pg.K_LSHIFT,), (pg.K_RSHIFT,))

    # gameplay
    PAINTER_SPEED = 5
    BASE_PAINTER_SPEED = 2
    PAINT_PER_PAINTER = 4
    PAINTER_PAINT_PER_PICKUP = 2
    MAX_PAINTER_SPEED = 10
    LEVEL_SIZE = (19 + 2, 9 + 2)
    COOLDOWN_TIME = 2
    PLAYER_SPEED = (.2, .5)
    PLAYER_MOVE_DELAY = 3 # as ratio of normal delay
    POSTGAME_INPUT_DELAY = 1.5

    # graphics
    RES_W = (1024, 576)
    PLAYER_COLOURS = ((228, 75, 36), (144, 87, 197))
    CHARGE_COLOUR = (100, 200, 100)
    LAYERS = {
        'bg': 1,
        'canvas': 0,
        'text': -1,
        'player': -1,
        'painter': -2,
        'particles': -3
    }
    # most args taken by the class
    PARTICLE_COLOURS = (
        [((177, 58, 28), 1), ((255, 95, 54), 1)],
        [((100, 60, 137), 1), ((194, 128, 255), 1)]
    )
    BURST_PARTICLES = (2000, (2.5, 1), (30, 20), (-3, 2), (1, .4))
    PARTICLE_FADE_TIME = .2 # proportion of life
    METER_WIDTH = 10
    SCORE_HEIGHT = 20
    MARGIN = 5
    REQUIRED_FONTS = dd({}, postgame = {'main': ('DenkOne-Regular.ttf', 80)})

    # audio
    MOVE_SOUND_FREQ = (.5, .2)
    SOUND_VOLUME = .5
    SOUND_VOLUMES = dd(1, move = .5, p1point = .2, p2point = .2, explode = 2)


conf.add(Conf.__dict__)
