import Levenshtein
ops = Levenshtein.editops("apple", "apo")
print(ops)
print(Levenshtein.distance("apple", "apo"))
