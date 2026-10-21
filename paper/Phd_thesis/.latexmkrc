# latexmk configuration for this thesis.
#
# Why this file exists:
#   1. latexmk's default target is DVI ($pdf_mode = 0).  Every figure in this
#      document is a .pdf, and the DVI backend cannot read a PDF's bounding
#      box, so a default-mode run dies with
#        ! LaTeX Error: Cannot determine size of graphic in Fig2.pdf
#      for all six figures.  Forcing $pdf_mode = 1 selects pdflatex.
#   2. A bare "pdflatex" (or "latex", "xelatex", "lualatex") typed on the
#      command line is not an option -- latexmk treats it as another input
#      file and reports "Could not find file 'pdflatex'".  The filter below
#      drops such a token so that
#        latexmk main.tex pdflatex
#      behaves like
#        latexmk -pdf main.tex
#
# Remove this file and use "latexmk -pdf main.tex" if you prefer no local
# configuration.

$pdf_mode = 1;

@ARGV = grep { !/^(pdf|xe|lua)?latex$/ } @ARGV;
