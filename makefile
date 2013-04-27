.PHONY: all clean distclean

all:
	CFLAGS="$(CFLAGS) `pkg-config --cflags sdl`" ./setup
	cp -a build/lib*/*.so game/engine/

clean:
	$(RM) -r build/ game/engine/*.so

distclean: clean
	find -regex '.*\.py[co]' -delete
