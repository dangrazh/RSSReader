#!"C:\strawberry\perl\bin\perl.exe"

use strict;
use warnings;
use Time::Piece;        # Time module to do time conversions
use DateTime;           # DateTime used to get the current timestamp
use LWP::UserAgent;     # "User Agent" (i.e. browser) module used for Web Processes
use XML::Parser;        # XML::Parser used to parse the RSS Feed (XML Feed) we get from web server
use Data::Dumper qw(Dumper);
use Encode;

my $exectimestmp;
my @rssout;
my @sortedout;

my $latest;
my $logmsg;
my $feeditem;
my $source;
my $url;
my $timezone;
my $priority;
my $timecut;


my $itmcount;
my $itmcountfeed;
my $skipon;
my $curritm;
my $descrdone;


##### 
# Main procedure
#####

    # Read the config information
    if (my $err = ReadCfg('./RSSReader.config')) {
        &writeLog(1, "", "", $err);
        exit(1);
    }

    my $interval = $CFG::CFG{'execintervalseconds'};

    if ($CFG::CFG{'run'} ne 'true') {
        &writeLog(1, "", "", "Stop exectuing scrip!");
        exit(1);
    }

    my $start = time;

    # do the download;
    &downloadfeeds;
    



##### 
# Doing the download
#####
sub downloadfeeds{

    # Open log file
    my $Logfile = "$CFG::CFG{'log'}{'file'}";
    if (! open(LOG, ">>$Logfile")) {
        print(STDERR "ERROR: Failure opening log file: $!\n");
        exit(1);
    }

    # Set the timestamps
    $exectimestmp = &set_now;
    my $execepoch = time();
    $timecut = $execepoch -  ($CFG::CFG{'minutesinscope'} * 60);

    # Load rss feed from web server
    my $agent = LWP::UserAgent->new;                   # Create me a browser
    $agent->agent("Mission-Control");                  # Set the browser name

    #initialize the item count
    $itmcount = -1;

    # Loop the sources and add content to the data store
    foreach my $feeditm (keys %{$CFG::CFG{'feeds'}}) {

            #get the configs
            $feeditem = $feeditm;
            $source = $CFG::CFG{'feeds'}{$feeditm}{'source'};
            $url = $CFG::CFG{'feeds'}{$feeditm}{'url'};
            $timezone = $CFG::CFG{'feeds'}{$feeditm}{'timezone'};
            $priority = $CFG::CFG{'feeds'}{$feeditm}{'priority'};


            my $req = HTTP::Request->new(GET => ($url)); 
            my $res = $agent->request($req);             
            my $page = $res -> content();                

            my $bytes = Encode::encode_utf8($page);

            open (FHO,">feedcontent_$source.txt");      # Save the raw XML (for debugging / analysing of data structure)
            print FHO $page;
            close FHO;

            open (FHFP,">feedparsed_$source.txt");       # Save the processed output (for debugging)
                    
            &writeLog(1, "", "", "Data read from $source done");

            #initialize the skip flag, the item count within the feed and the current item
            $skipon = 0;
            $curritm = '';
            $itmcountfeed = 0;

            # parsing and selecting tags handled in &\handle_char
            my $parser = new XML::Parser(Handlers => {Start => \&entering, Char  => \&handle_char});
            $parser -> parse($bytes);

            &writeLog(1, "", "", "Data $source parsed");
            close FHFP;
    }


    #make sure every epoch time field has a valid time stamp in it
    &completetime;

    #sort by the epoch time (which is in field 5 of the array) descending
    #note that $a and $b are inversed, which gives the descending order
    @sortedout = sort { $b->[5] <=> $a->[5] } @rssout;

    #create the ouput 
    &createoutput;

    &writeLog(1, "", "", "Output written - Processing completed");
    close LOG;

}


#############################
# Handlers for XLM::Parser
#############################

sub entering {
        $latest = $_[1];
        }

sub handle_char {

        if ($latest eq "guid") {
            do_pars("url", @_);
        }
        if ($latest eq "title") {
            do_pars("title", @_);
        }
        if ($latest eq "description") {
            do_pars("description", @_);
        }
        if ($latest eq "pubDate") {
            do_pars("pubDate", @_);
        }
}

sub say_pars {
        my($what,$obj,$el) = @_;
        return unless ($el =~ /\S+/);
        print "$el\n";
}

sub do_pars {
        my($what,$obj,$el) = @_;
        return unless ($el =~ /\S+/);

        ######
        #here comes the logic to store the content in an array or hash construct
        ######

        if ($what eq "text" or $what eq "title") {
            if (exists $CFG::CFG{'feeds'}{$feeditem}{'skip'}{$el}) {
                    #skip
                    #print "$what: skipped!\n";
                    #need to remember that this is now a skipped entry including all subsequent elements
                    $skipon = 1;
                    $curritm = $el;
                    &writeLog(2, $what, "    [skipped skip check]", "src -> $source | ic -> $itmcount | so -> $skipon | cri -> $curritm | '$el'");
            } else {
                    if ($curritm eq $el) {
                        if ($skipon){
                            #we are still in the same item, skip this 
                            &writeLog(2, $what, "    [skipped skipon ci==el]", "src -> $source | ic -> $itmcount | so -> $skipon | cri -> $curritm | '$el'");
                        } else {
                            #process the item
                            $itmcount++;
                            $itmcountfeed++;
                            $rssout[$itmcount][0] = $source;
                            $rssout[$itmcount][1] = $el;
                            $rssout[$itmcount][6] = $itmcountfeed;
                            $skipon = 0;
                            $descrdone = 0;
                            $curritm = $el;        
                            #print FHFP "$itmcount: $what: $el\n";
                            #&writeLog(2, $what, "    [processed  to file - ci==el]", "src -> $source | ic -> $itmcount | so -> $skipon | cri -> $curritm | '$el'");
                        }
                    } else {
                        #this is a new item
                        #process the item
                        $itmcount++;
                        $itmcountfeed++;
                        $rssout[$itmcount][0] = $source;
                        $rssout[$itmcount][1] = $el;
                        $rssout[$itmcount][6] = $itmcountfeed;
                        $skipon = 0;
                        $descrdone = 0;                        
                        $curritm = $el;        
                        #print FHFP "$itmcount: $what: $el\n";
                        #&writeLog(2, $what, "    [processed  to file - ci<>el]", "src -> $source | ic -> $itmcount | so -> $skipon | cri -> $curritm | '$el'");

                    }

            }            
        } elsif ($what eq "pubDate") {
            #if ($curritm eq $el) {
                if ($skipon){            
                    # skip it
                    #&writeLog(2, $what, "    [skipped skipon che]", "src -> $source | ic -> $itmcount | so -> $skipon | cri -> $curritm | '$el'");
                } else {
                    if ($CFG::CFG{'feeds'}{$feeditem}{'timezone'} eq 'UTC') {
                        $rssout[$itmcount][4] = &get_date($el, '%a, %d %b %Y %H:%M:%S %z');
                        $rssout[$itmcount][5] = &get_epoch($el, '%a, %d %b %Y %H:%M:%S %z');
                        #print FHFP "$itmcount: $what: " . &get_epoch($el, '%a, %d %b %Y %H:%M:%S %z') . "\n";
                        #&writeLog(2, $what, "    [processed  to file]", "src -> $source | ic -> $itmcount | so -> $skipon | cri -> $curritm | '$el'");
                    }
                    if($CFG::CFG{'feeds'}{$feeditem}{'timezone'} eq 'GMT') {                        
                        $rssout[$itmcount][4] = &get_date($el, '%a, %d %b %Y %H:%M:%S %Z');
                        $rssout[$itmcount][5] = &get_epoch($el, '%a, %d %b %Y %H:%M:%S %Z');
                        #print FHFP "$itmcount: $what: " . &get_epoch($el, '%a, %d %b %Y %H:%M:%S %Z') . "\n";
                        #&writeLog(2, $what, "    [processed  to file]", "src -> $source | ic -> $itmcount | so -> $skipon | cri -> $curritm | '$el'");
                    }
                }
            #} 
        } else {
            
            if ($skipon){
                # skip it
                #&writeLog(2, $what, "    [skipped skipon che]", "src -> $source | ic -> $itmcount | so -> $skipon | cri -> $curritm | '$el'");
            } else {                
                if ($what eq 'description'){
                    if($source eq 'Reuters') {
                        if ($descrdone) {
                            #skip it
                        } elsif ($el eq '<') {
                            $descrdone = 1;
                        } else {
                            $rssout[$itmcount][2] = $el;
                        }
                    } else {
                        $rssout[$itmcount][2] = $el;
                    }
                }
                if ($what eq 'url'){
                    if($source eq 'Reuters') {
                        $rssout[$itmcount][3] = $rssout[$itmcount][3] . $el;
                    } else {
                        $rssout[$itmcount][3] = $el;   
                    }
                }

                #print FHFP "$itmcount: $what: $el\n";
                #&writeLog(2, $what, "    [processed  to file]", "src -> $source | ic -> $itmcount | so -> $skipon | cri -> $curritm | '$el'");
            }
        }
        
}


#############################
# Date & Time routines
#############################
sub say_now {

        my $dt   = DateTime->now;   
        my $date = $dt->ymd;   
        my $time = $dt->hms;   

        my $wanted = "$date $time";   
        print $wanted;

}

sub set_now {

        my $dt   = DateTime->now;   
        my $date = $dt->ymd;   
        my $time = $dt->hms;   

        my $wanted = "$date $time";  
        return $wanted;

}


sub get_date { # get a date time object from date / time string 
                # arg1 -> date time string
                # arg2 -> pattern mask as per POSIX Function strftime() definition

    my $source = shift;
    my $format = shift;
    my $time   = Time::Piece->strptime ($source, $format);
    my $timeout = $time->datetime();
    return $timeout;

}

sub get_epoch { # get the epoch time from date / time string 
                # arg1 -> date time string
                # arg2 -> pattern mask as per POSIX Function strftime() definition

    my $source = shift;
    my $format = shift;
    my $time   = Time::Piece->strptime ($source, $format);
    my $epoch  =  $time ->epoch();
    return $epoch;

}




#############################
# Config routines
#############################

# Read a configuration file
# The arg can be a relative or full path, or
# it can be a file located somewhere in @INC.
sub ReadCfg
{
    my $file = $_[0];

    our $err;

    {   # Put config data into a separate namespace
        package CFG;

        # Process the contents of the config file
        my $rc = do($file);

        # Check for errors
        if ($@) {
            $::err = "ERROR: Failure compiling '$file' - $@";
        } elsif (! defined($rc)) {
            $::err = "ERROR: Failure reading '$file' - $!";
        } elsif (! $rc) {
            $::err = "ERROR: Failure processing '$file'";
        }
    }

    return ($err);
}


#############################
# Service Routines
#############################

sub completetime {

    #Counter for the array loop
    my $n = 0;
    my $n1 = 0;
    my $source;

    #Loop the array and fix missing time stamps
    while ($rssout[$n][0]) {

        if (! defined $rssout[$n][5]) {

            #print "fixing missing time stamp at position $n\n";
            #get the next item in the feed  with data in 
            $n1 = $n + 1;
            $source = $rssout[$n][0];
            while (! defined $rssout[$n1][5] and $rssout[$n1][5] eq $source) {
                $n1++;
            }
            
            if ($rssout[$n][6] == 1) {
                # this is the 1st item in the feed, use the next item's
                # time stamp and reduce by 1
                $rssout[$n][5] = $rssout[$n1][5] - 1;

            } elsif ($rssout[$n+1][6] == 1 or $n1 == ($n + 1)) {
                # this is the last item in the feed or none of the subsequent
                # items had a valid time stamp, use the previous item's 
                # time stamp and increase by 1
                $rssout[$n][5] = $rssout[$n-1][5] + 1;

            } else {
                # this is the nth entry in the feed calculate the middle
                # between the last item and the next valid item
                $rssout[$n][5] = int(($rssout[$n-1][5] + $rssout[$n1][5]) / 2);
            }

        }

        $n++;
    }


}



sub createoutput {

    print  "content-type: text/html \n\n";
    
    #Set up the HTML page
    print "<html>\n";
    print "<head>\n<title>Mission Control News Feed</title>\n";
    print "<meta http-equiv=\"refresh\" content=\"$interval\">\n";
    print "<META NAME=\"Cache-Content\" CONTENT=\"no_cache\">\n";
    print "<style>\nbody {background-color: #212729;font-family: sans-serif;}\n</style>\n</head>\n";    #antracite 25% darker

    print "<body text =\"LightGrey\">\n";
    print "<p align=\"right\"><font size=\"2px\">Last refreshed: $exectimestmp<br />News of last $CFG::CFG{'minutesinscope'} minutes displayed, refreshed every $interval seconds.</p>";
    print "<table border=\"1\">\n";
    print "<col width=\"50\">\n<col width=\"440\"><col width=\"940\"><col width=\"80\"><col width=\"160\">\n";
    print "<tr style=\"font-weight:bold\"><td>Source</td><td>Title</td><td>Description</td><td>Link</td><td>Published</td></tr>\n";

    #Counter for the array loop
    my $n = 0;

    #Loop the array
    while ($sortedout[$n][0]) {


        #check if entry is in time frame we want to output
       if($sortedout[$n][5] > $timecut) {
            my $col0 = $sortedout[$n][0];
            my $col1 = $sortedout[$n][1];
            my $col2 = $sortedout[$n][2];
            my $col3 = $sortedout[$n][3];
            my $col4 = $sortedout[$n][4];

            print "<tr><td>$col0</td><td>$col1</td><td>$col2</td><td><a href=\"$col3\"><div style=\"height:100%;width:100%\">link</div></a></td><td>$col4</td></tr>\n";
           
       }
        $n++;
    }

    print "</table>\n";
    print "</body>\n";

}



sub writeLog
{
    
    my $loglevel = shift;
    my $logwhat = shift;
    my $logactivity = shift;
    my $logmsgin = shift;
    my $logtmstmp = &set_now;
    my $whatfmt;

    $whatfmt = $logwhat . ' ' x 10;
    $whatfmt = substr $whatfmt, 0, 11;

    if ($loglevel <= $CFG::CFG{'log'}{'level'}) {
        print LOG "$logtmstmp: <$whatfmt> $logactivity $logmsgin\n";
    }
}