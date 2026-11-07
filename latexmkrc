# Root Overleaf proxies keep bibliography/style sources in paper/.
# Preserve caller-provided search paths and TeX's default path (trailing colon).
$ENV{'BIBINPUTS'} = './paper//:' . ($ENV{'BIBINPUTS'} // '');
$ENV{'BSTINPUTS'} = './paper//:' . ($ENV{'BSTINPUTS'} // '');
