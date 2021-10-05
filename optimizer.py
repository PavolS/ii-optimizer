#!/usr/bin/env python3

import argparse
import functools
import json
import copy
import math

class Channel:
    def __init__(self, name, **kwargs):
        self.name = name
        self.c0 = kwargs["cost"]["initial"]
        self.r = kwargs["cost"]["rate"]
        self.t = kwargs["reward"]["duration"]
        self.views = kwargs["reward"]["views"]
        self.p = kwargs["reward"]["revenue"]
        self.lvl = kwargs["level"]
        self.multipliers = {int(k): int(v) for k,v in kwargs["multipliers"].items()}
        self.multiplier = 1

    def upgrade(self):
        self.lvl+=1
        self.multiplier*=self.multipliers.get(self.lvl, 1)
        return self.t

    def degrade(self):
        self.multiplier/=self.multipliers.get(self.lvl, 1)
        self.lvl-=1

    @functools.lru_cache()
    def cost(self):
        return self.c0 * (self.r**self.lvl)

    @functools.lru_cache()
    def cash_out(self):
        return self.views*self.p*self.multiplier*self.lvl

    def till_cash_out(self, t):
        return self.t - t % self.t

    def since_cash_out(self, t):
        return t % self.t

    @functools.lru_cache()
    def income(self):
        return self.cash_out()/self.t

    def __str__(self):
        return "{name}@{lvl}({income} $/s, {cost})".format(income=self.income(), cost=self.cost(), **vars(self))

    def __repr__(self):
        return str(self)

    def __hash__(self):
        # NOTE: This is a perfect hash when combined with type and useless otherwise
        return self.lvl

class Channels:
    def __init__(self, channels_iterable):
        self._channels = list(c for c in channels_iterable)
        self._channels_orig = copy.deepcopy(self._channels)

    @property
    def channels(self):
        return self._channels

    @property
    def lvls(self):
        return tuple(c.lvl for c in self.channels)

    @functools.lru_cache()
    def income(self):
        return sum(c.income() for c in self.channels)

    def upgrade(self, i):
        self._channels[i].upgrade()

    def degrade(self, i):
        self._channels[i].degrade()

    def get_time_and_money_for_next_cashout(self, t):
         return min( (c.t - t % c.t, c.cash_out()) for c in self.channels)

    @functools.lru_cache()
    def min_cost(self):
        return min(c.cost() for c in self.channels)

    @functools.lru_cache()
    def max_cost(self):
        return max(c.cost() for c in self.channels)

    def t_rems(self, t):
        return tuple(math.floor( (t % c.t) * 10 ) for c in self.channels)

    def __hash__(self):
        return hash(self.lvls)

    def upgradeAt(self, i, cash, t):
        cu = self.channels[i]
        #print("Upgrade {} for {}".format(i, cu.cost()))

        while cash < cu.cost():
            dt, dc = self.get_time_and_money_for_next_cashout(t)
            cash += dc
            t += dt + EPSILON
        cu.upgrade()
        cash-=cu.cost()
        return cash, t

    def print_path_result(self, path):
        _channels = copy.deepcopy(self)
        _channels._channels = copy.deepcopy(self._channels_orig)
        for i, _t in path:
            _channels.upgrade(i)
        print("{:.1f}:\tIncome={:.0f}$/s channels={}".format(_t, _channels.income(), [ str(c) for c in _channels.channels]))
        
class LookupStorage:
    def __init__(self):
        self.data = {}

    def key(self, channels, cash, t):
        _channels = channels.lvls
        _cash = math.floor(cash % channels.max_cost() / channels.min_cost() )
        _t = channels.t_rems(t)
        return (_t, _cash, _channels)

    def store(self, key, value):
        self.data[key] = value

    def lookup(self, channels, cash, t):
        key = self.key(channels, cash, t)
        return key, self.data.get(key)

BOUND = None
EPSILON = 1e-3
WORST = 1e999
best = WORST
mem = LookupStorage()

def optimize(channels, cash, t, path):
    global best
    global mem

    key, value = mem.lookup(channels, cash, t)
    if value:
        return value

    if t > best:
        return WORST, path

    income = channels.income()

    if income < BOUND:
        options = []
        for i, _ in enumerate(channels.channels):
            cash_new, t_new = channels.upgradeAt(i, cash, t)
            options.append( optimize(channels, cash_new, t_new, path + [(i, t_new)] ) )
            channels.degrade(i)
        t, path = min( options, key = lambda r: r[0] )
        if t < best:
            best = t
            channels.print_path_result(path)

    mem.store(key, (t, path))

    return t, path

def main(defs_path, bound):
    global BOUND
    BOUND = bound
    channels = []
    for name, data in json.load(open(defs_path)).items():
        channels.append(Channel(name, **data))

    print("Starting with following channels:", channels)

    channels = Channels(channels)
    t, path =  optimize(channels, EPSILON, EPSILON, [])
    print("BEST: ", t, [i for i, t in path])
    channels.print_path_result(path)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument('--defs', '-d', default="./defs.json", help="Definitions for channel (akak generators)")
    p.add_argument('income', type=int, default=200, help="Goal to reach in terms of income [$/s]")
    args = p.parse_args()
    main(args.defs, args.income)