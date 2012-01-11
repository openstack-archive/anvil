#!/usr/bin/perl -w

use warnings;
use strict;

use FileHandle;
use Term::ANSIColor qw(:constants);


sub printinfo 
{
    print BOLD, BLUE, "INFO: "."", RESET;
    println("@_");
}

sub printerror
{
    print BOLD, RED, "ERROR: @_"."\n", RESET;
}

sub run
{
    my ($prog, $die) = @_;
    #printinfo("Runing command: $prog");
    my $res = qx/$prog/;
    my $ok = 0;
    my $rc = $? >> 8;
    if($rc == 0)
    {
        $ok = 1;
    }
    if($ok == 0 && $die == 1)
    {
        printerror("Failed running $prog");
        exit(1);
    }
    $res = trim($res);
    my $out = {};
    $out->{'status'} = $rc;
    $out->{'output'} = $res;
    return $out;
}

sub println
{
    my $arg = shift;
    if(!defined($arg))
    {
        $arg = '';
    }
    return print($arg."\n");
}

sub trim
{
	my $string = shift;
	$string =~ s/^\s+//;
	$string =~ s/\s+$//;
	return $string;
}

my $argc = scalar(@ARGV);
if($argc == 0)
{
    println($0. " pkglist");
    exit(1);
}   


my $fn = $ARGV[0];
my $fh = new FileHandle($fn, "r") || die("Could not open $fn");;
my @lines = <$fh>;
$fh->close();

my @all = ();
my $ks = {};

for my $line (@lines)
{
    $line = trim($line);
    if(length($line) == 0)
    {
        next;
    }
    my @pieces = split /\s+/, $line;
    for my $piece (@pieces)
    {
        $piece = trim($piece);
        if(length($piece) == 0)
        {
            next;
        }
        if(defined($ks->{$piece}))
        {
            next;
        }
        push(@all, $piece);
        $ks->{$piece} = 1;
    }
}

@all = sort(@all);
printinfo("Finding info about packages:");
println(join(", ", @all)."");

my $info  = {};
for my $pkg (@all)
{
    printinfo("Finding information about $pkg");
    my $cmd = "apt-cache showpkg $pkg";
    my $out = run($cmd, 1)->{'output'};
    my $version = undef;
    if($out =~ /Versions:\s+([\S]+)\s+/msi)
    {
        $version = $1;
    }
    else
    {
        printerror("No version found for $pkg");
        exit(1);
    }
    $cmd = "apt-cache depends $pkg";
    $out = run($cmd, 1)->{'output'};
    my @tmplines = split /\n|\r/, $out;
    my @deps = ();
    for my $aline (@tmplines)
    {
        if($aline =~ /\s+Depends:\s*(\S+)\s*/i)
        {
            my $dep = trim($1);
            if(length($dep) > 0)
            {
                if($dep =~ /[<>]/)
                {
                    #not sure why we get these...
                    next;
                }
                push(@deps, $dep);
            }
        }
    }
    my $d = {};
    $d->{'deps'} = \@deps;
    $d->{'version'} = $version;
    $info->{$pkg} = $d;
}

for my $pkg (@all)
{
   my $data = $info->{$pkg};
   my $version = $data->{version};
   print STDERR ("+Package name: $pkg\n");
   print STDERR ("+Package version: $version\n");
   my @deps = @{$data->{deps}};
   @deps = sort(@deps);
   my $tmpk = {};
   print STDERR  ("+Dependencies:\n");
   for my $dep (@deps)
   {
       if(defined($tmpk->{$dep}))
       {
           next;
       }
       print STDERR ("\t"."$dep\n");
       $tmpk->{$dep} = 1;
   }
}

exit(0);

