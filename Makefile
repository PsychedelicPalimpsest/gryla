CC    = gcc
CFLAGS  = -g
RM      = rm -f

LIB_CFLAGS = $(CFLAGS) -fPIC


LIB_SRC = $(wildcard lib/*.c)
LIB_OBJS = $(LIB_SRC:.c=.o)



lib: libgryla.so


libgryla.so : $(LIB_OBJS)
	$(CC) $(LIB_CFLAGS) -shared -o libgryla.so $(LIB_OBJS)

lib/%.o : lib/%.c
	$(CC) $(LIB_CFLAGS) -c $< -o $@ 

bear:
	bear -- make

clean:
	$(RM) $(LIB_OBJS)
	
