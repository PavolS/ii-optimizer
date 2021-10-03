#!/usr/bin/env python3

import argparse
import json
import sys
import math
from pprint import pprint

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

    def cost(self):
        return self.c0 * (self.r**self.lvl)

    def cash_out(self):
        return self.views*self.p*self.multiplier*self.lvl

    def till_cash_out(self, t):
        return self.t - t % self.t

    def since_cash_out(self, t):
        return t % self.t

    def income(self):
        return self.cash_out()/self.t

    def __str__(self):
        return "{name}@{lvl}({income} $/s, {cost})".format(income=self.income(), cost=self.cost(), **vars(self))

    def __repr__(self):
        return str(self)

class LookupStorage:
    def __init__(self):
        self.data = {}

    def key(self, channels, cash, t):
        _channels = (c.lvl for c in channels)
        # _cash = math.floor(cash*100)
        # _t = math.floor(t*100)
        _cash = 0
        _t = 0
        return (_t, _cash, _channels)

    def store(self, key, value):
        self.data[key] = value

    def lookup(self, channels, cash, t):
        key = self.key(channels, cash, t)
        return key, self.data.get(key)

BOUND = 4
EPSILON = 1e-3
best = 1e99
mem = LookupStorage()

def total_income(channels):
    return sum(c.income() for c in channels)

def _upgradeAt2(*args):
    channels, i, cash, t, income = args
    cu = channels[i]

    if cash >= cu.cost():
        cu.upgrade()
        return cash - cu.cost(), t

    dt0 = (cu.cost() - cash) / income
    cash += sum( math.floor( (c.since_cash_out(t) + dt0) / c.t ) * c.cash_out() for c in channels )
    t += dt0

    return _upgradeAt(channels, i, cash, t, None)



def _upgradeAt(*args):
    channels, i, cash, t, _ = args
    cu = channels[i]
    #print("Upgrade {} for {}".format(i, cu.cost()))

    while cash < cu.cost():
        dt, dc = min( (c.t - t % c.t, c.cash_out()) for c in channels)
        cash += dc
        t += dt + EPSILON
    cu.upgrade()
    cash-=cu.cost()
    return cash, t

def _upgradeAt3(*args):
    channels, i, cash, t, income = args
    channels[i].upgrade()
    return cash, t + channels[i].cost()/income

UPGRADE_AT={
    1: _upgradeAt,
    2: _upgradeAt2,
    3: _upgradeAt3
}

def optimize(channels, cash, t, path, upgradeAt):
    global best
    global mem

    key, value = mem.lookup(channels, cash, t)
    if value:
        print("MATCH!")
        return value

    income = total_income(channels)

    if t > best:
        return 1e99, path

    if income < BOUND:
        options = []
        for i, _ in enumerate(channels):
            cash_new, t_new = upgradeAt(channels, i, cash, t, income)
            options.append( optimize(channels, cash_new, t_new, path + [(i, t_new)], upgradeAt ) )
            channels[i].degrade()
        t, path = min( options, key = lambda r: r[0] )
        if t < best:
            print("best so far: ", t)
            pprint(path)
            best = t

    mem.store(key, (t, path))

    return t, path



def main(defs_path, bound, upat_key):
    global BOUND
    BOUND = bound
    channels = []
    for name, data in json.load(open(defs_path)).items():
        channels.append(Channel(name, **data))

    print("Starting with following channels:", channels)

    t, path =  optimize(channels, EPSILON, EPSILON, [], UPGRADE_AT[upat_key])
    print("BEST: ", t)
    pprint(path)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument('--defs', '-d', default="./defs.json", help="Definitions for channel (akak generators)")
    p.add_argument('--upgrade_at', '-u', default=1, type=int, help="define upgradeAt method to use" )
    p.add_argument('income', type=int, default=200, help="Goal to reach in terms of income [$/s]")
    args = p.parse_args()
    main(args.defs, args.income, args.upgrade_at)