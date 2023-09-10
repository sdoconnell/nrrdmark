PREFIX = /usr/local
BINDIR = $(PREFIX)/bin
MANDIR = $(PREFIX)/share/man/man1
DOCDIR = $(PREFIX)/share/doc/nrrdmark
BSHDIR = /etc/bash_completion.d

.PHONY: all install uninstall

all:

install:
	install -m755 -d $(BINDIR)
	install -m755 -d $(MANDIR)
	install -m755 -d $(DOCDIR)
	install -m755 -d $(BSHDIR)
	gzip -c doc/nrrdmark.1 > nrrdmark.1.gz
	install -m755 nrrdmark/nrrdmark.py $(BINDIR)/nrrdmark
	install -m644 nrrdmark.1.gz $(MANDIR)
	install -m644 README.md $(DOCDIR)
	install -m644 CHANGES $(DOCDIR)
	install -m644 LICENSE $(DOCDIR)
	install -m644 CONTRIBUTING.md $(DOCDIR)
	install -m644 auto-completion/bash/nrrdmark-completion.bash $(BSHDIR)
	rm -f nrrdmark.1.gz

uninstall:
	rm -f $(BINDIR)/nrrdmark
	rm -f $(MANDIR)/nrrdmark.1.gz
	rm -f $(BSHDIR)/nrrdmark-completion.bash
	rm -rf $(DOCDIR)

