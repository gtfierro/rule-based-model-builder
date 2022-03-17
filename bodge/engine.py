import csv
from warnings import warn
import re
import json
import tempfile
from inspect import getclosurevars as closure_vars
from inspect import getmembers
from collections import defaultdict

#TODO: if tag is rawstring, treat as regex?
rules = []
fixedpoint_rules = []
iterations = defaultdict(lambda : defaultdict(int))
last_run = defaultdict(int)

def any_changed():
    """returns True if any fixedpoint rules changed"""
    if len(iterations) == 0:
        print("No iters yet; continuing")
        return True
    for key, values in iterations.items():
        # if 0 or 1 iterations, we don't know if anything has changed yet
        if len(values) < 2:
            print("Not enough iters; continuing", key)
            return True
        ult_val = values[len(values)-1]
        penult_val = values[len(values)-2]
        if ult_val >  penult_val and ult_val > last_run[key]:
            print(f"Rule {key} triggered", ult_val, penult_val)
            last_run[key] = ult_val
            return True
    return False


def fixedpoint(*vs):
    def _outer(func):
        func_name = dict(getmembers(func))['__qualname__']
        def f(*args):
            print("trigger", args)
            # (nonlocals, globals, builtins, unbound)
            (_, closed, _, _) = closure_vars(func)
            res = func(*args)
            for varname in vs:
                if varname not in closed:
                    continue
                value = closed.get(varname)
                iter_num = len(iterations[(func_name, varname)])
                iterations[(func_name, varname)][iter_num] = len(value)
                print((func_name, varname), iter_num, len(value))
            return res
        f.__fixedpoint__ = True
        return f
    return _outer


def tags(*tags):
    def _matches(func):
        def f(row):
            # match the tags
            for tag in tags:
                if tag not in row.keys() or not row[tag]:
                    return None
            return func(row)
        if getattr(func, "__fixedpoint__", False):
            fixedpoint_rules.append(f)
        rules.append(f)
        return f
    return _matches

def fun(fn, *args):
    def _matches(func):
        def f(row):
            # match the tags
            try:
                if fn(row, *args):
                    return func(row)
            except Exception as e:
                warn(f"Error in rule {func}: {e}")
        if getattr(func, "__fixedpoint__", False):
            fixedpoint_rules.append(f)
        rules.append(f)
        return f
    return _matches

def values(value_pairs):
    def _matches(func):
        def f(row):
            # match the tags
            for (tag, value) in value_pairs.items():
                if tag not in row.keys():
                    return None
                if row[tag] != value:
                    return None
            return func(row)
        if getattr(func, "__fixedpoint__", False):
            fixedpoint_rules.append(f)
        rules.append(f)
        return f
    return _matches

def value_matches(value_pairs):
    def _matches(func):
        def f(row):
            # match the tags
            for (tag, value) in value_pairs.items():
                if tag not in row.keys():
                    return None
                if not re.match(value, row[tag]):
                    return None
            return func(row)
        if getattr(func, "__fixedpoint__", False):
            fixedpoint_rules.append(f)
        rules.append(f)
        return f
    return _matches

def oneof(*tags):
    s = set(tags)
    def _matches(func):
        def f(row):
            if len(set(row.keys()).intersection(s)) > 0:
                return func(row)
            return None
        if getattr(func, "__fixedpoint__", False):
            fixedpoint_rules.append(f)
        rules.append(f)
        return f
    return _matches


def _and_(*_conds):
    def _matches(func):
        conds = []
        for _cond in _conds:
            cond = _cond[0](*_cond[1:])(lambda x: True)
            conds.append(cond)
        def f(row):
            for cond in conds:
                if cond(row) is None:
                    return None
            return func(row)
        if f is not None:
            if getattr(func, "__fixedpoint__", False):
                fixedpoint_rules.append(f)
            rules.append(f)
        return f
    return _matches


class Stream:
    def __init__(self):
        pass

    def setup(self):
        raise NotImplemented("setup not implemented")

    def next(self):
        raise NotImplemented("next not implemented")

    def __iter__(self):
        self.setup()
        return self

    def __next__(self):
        return self.next()


class CSVFileStream(Stream):
    def __init__(self, filename):
        self.fname = filename

    def setup(self):
        self.f = open(self.fname)
        self.rdr = csv.DictReader(self.f)

    def next(self):
        return next(self.rdr)

class JSONFileStream(Stream):
    def __init__(self, filename):
        self.fname = filename

    def setup(self):
        self.f = iter(json.load(open(self.fname)))

    def next(self):
        return next(self.f)

def drive(*streams):
    # apply each rule on each row in each stream once
    for stream in streams:
        for row in stream:
            if row is None:
                continue
            for rule in rules:
                rule(row)
    print('fixed point rules?', fixedpoint_rules)
    while any_changed() and len(fixedpoint_rules) > 0:
        for stream in streams:
            for row in iter(stream):
                if row is None:
                    continue
                for rule in fixedpoint_rules:
                    rule(row)
