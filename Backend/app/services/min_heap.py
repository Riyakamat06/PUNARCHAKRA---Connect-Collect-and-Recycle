"""
min_heap.py  -  Engine 2 (Logic and Rule)  -  hand-built min-heap for "top k".

WHAT THIS FILE DOES
    Keeps only the BEST k items out of many, without sorting all of them.
    The ranking needs the top 10 dealers out of n eligible dealers.

THE IDEA (simple words)
    A min-heap is a list arranged like a tree where the WEAKEST item is always
    at the top (position 0, called the root). We keep at most k items in it:
      * While the heap has fewer than k items, just add the new one.
      * When it is full, compare the new item with the root (the weakest of
        our current best k). If the new one is better, throw the root away and
        put the new one in. If not, ignore the new one.
    At the end the heap holds exactly the best k items.

    Each item is a pair (key, payload).
      key     = a tuple that says how good the item is. BIGGER key = BETTER.
                Python compares tuples left to right, so the first value
                decides, and the next value is used only on a tie.
      payload = the data we want back (the dealer's details).

COMPLEXITY
    Adding one item costs O(log k). For n items the total is O(n log k).
    With k = 10 this is about O(n * 3.3), so close to linear in n.
    The final sort of the k survivors costs O(k log k), which is tiny.

WHY WRITTEN BY HAND
    The Gate 2 design says the heap is built by hand (not Python's heapq),
    so that the Data Structures part of the project is visible in the code.
"""


class MinHeap:
    """A min-heap that never holds more than max_size items."""

    def __init__(self, max_size):
        if max_size < 1:
            raise ValueError("max_size must be at least 1")
        self.max_size = max_size
        # The tree is stored in a plain list. For the item at position i:
        #   its parent is at   (i - 1) // 2
        #   its children are at 2*i + 1  and  2*i + 2
        self._items = []

    def __len__(self):
        return len(self._items)

    def push_top_k(self, key, payload):
        """Offer one item to the heap. Keep it only if it is among the best k."""
        if len(self._items) < self.max_size:
            # Heap not full yet: add at the end, then move it up into place.
            self._items.append((key, payload))
            self._sift_up(len(self._items) - 1)
        elif key > self._items[0][0]:
            # Heap is full and the new item beats the weakest one (the root):
            # replace the root, then move the new item down into place.
            self._items[0] = (key, payload)
            self._sift_down(0)
        # Otherwise the new item is weaker than all k we hold: ignore it.

    def best_first(self):
        """Return the stored items as a list, best item first."""
        # Only k items are left, so this sort is cheap: O(k log k).
        return sorted(self._items, key=lambda item: item[0], reverse=True)

    # ---- internal helpers -------------------------------------------------

    def _sift_up(self, i):
        """Move item i up while it is weaker than its parent (weakest on top)."""
        while i > 0:
            parent = (i - 1) // 2
            if self._items[i][0] < self._items[parent][0]:
                self._items[i], self._items[parent] = self._items[parent], self._items[i]
                i = parent
            else:
                break

    def _sift_down(self, i):
        """Move item i down while a child is weaker than it."""
        n = len(self._items)
        while True:
            left, right = 2 * i + 1, 2 * i + 2
            weakest = i
            if left < n and self._items[left][0] < self._items[weakest][0]:
                weakest = left
            if right < n and self._items[right][0] < self._items[weakest][0]:
                weakest = right
            if weakest == i:
                break
            self._items[i], self._items[weakest] = self._items[weakest], self._items[i]
            i = weakest