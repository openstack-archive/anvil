for i in `find . -name "*.py"`
do
	perl -i -pe "BEGIN{undef $/;} s/if\s*\(\s*(.*?)\s*\)\s*:/if \$1:/sg" $i
done
