#!/usr/bin/env python3
# -*- coding: utf-8 -*-

try:
    import Queue as Q  # ver. < 3.0
except ImportError:
    import queue as Q
   
from typing import Any, Callable
from dataclasses import dataclass, field

# default scorer
def uniform_scorer(item: Any) -> int:
    return 1

@dataclass(order=True)
class PrioritizedItem:
    """ Wrapper class adding integer priority for items stored in queue."""
    priority: int
    item: Any=field(compare=False)
    
class ScoringPriorityQueue:
    """ Simple utility class representing prioirty queue with score function """
    def __init__(self, scorer: Callable = None):
        self.queue = Q.PriorityQueue()
        self.scorer = scorer if scorer else uniform_scorer
    
    def set_scorer(self, scorer: Callable) -> None:
        self.scorer = scorer
        
    def size(self):
        return self.queue.qsize()
    
    def push(self, item: Any) -> None:
        score = self.scorer(item)
        self.queue.put(PrioritizedItem(score, item))
        
    def get_next(self) -> Any:
        if not self.queue.empty():
            return self.queue.get().item
        else:
            return None
        
    # For debugging   
    def debug_contents(self, with_score=False):
        contents = []
        while not self.queue.empty():
            obj = self.queue.get()
            contents.append((obj.priority, obj.item))
        
        for score,item in contents:
            self.queue.put(PrioritizedItem(score, item))
            
        if with_score:
            return contents
        else:
            return [c[1] for c in contents]