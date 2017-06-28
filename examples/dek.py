funkcje = []
def dekorator(func):
    funkcje.append(func)
    return func

@dekorator
def lel():
    print('Hello')

lel()
print(funkcje)