
class Dict(dict):
    def __getattr__(self, key):
        try: return self[key]
        except KeyError: return object.__getattribute__(self, key)
    def __setattr__(self, key, value):
        self[key] = value
 
