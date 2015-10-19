CC ?= clang

all:: $(patsubst %.c,%.bc,$(wildcard *.c))

%.bc : %.c
	$(CC) -emit-llvm -c -std=c99 -O0 -g -o $@ $<

.PHONY: clean

clean:
	rm -f $(wildcard *.bc)
