'''

The scATAC-seq data comes as three files, P1, P2 and the barcode, and there is no UMI

You can just align P1 and P2 with your favourite aligner (we prefer STAR with these settings):

****
teopts=' --outFilterMultimapNmax 100 --winAnchorMultimapNmax 100 --outSAMmultNmax 1 --outSAMtype BAM SortedByCoordinate --twopassMode Basic --outWigType wiggle --outWigNorm RPM'
opts='--runRNGseed 42 --runThreadN 12 --readFilesCommand zcat '

genome_mm10='--genomeDir mm10_gencode_vM21_starsolo/SAindex'
genome_hg38='--genomeDir hg38_gencode_v30_starsolo/SAindex'

# p1 = read
# p2 = barcode and UMI
# Make sure you set the correct genome index;
STAR $opts $teopts $genome_hg38 --outFileNamePrefix ss.${out} --readFilesIn ${p1} ${p2}
****

This script will then reprocess the BAM file, and put the BARCODE into CR SAM tag and spoof a UMI

The UMI is generated by incrementing the sequence, so, each UMI is up to 4^14 (26 million).
I guess there remains a change of a clash, but it should be so rare as to be basically impossible.

Require pysam


See also: bin/pack_scatacseq

'''

import sys,os
import gzip
import argparse
import logging
import dbm
import time
import random

try:
    import pysam
except ImportError:
    pass # fail silently

def generate_mismatches(seq):
    """
    **Purpose**
        Generate all 1 bp mismatches for the sequence
    """
    newseqs = []

    for pos in range(len(seq)):
        newseqs += list(library([[i] for i in seq[0:pos]] + ["ACGT"] + [[i] for i in seq[pos:-1]]))

    return set(newseqs)

def fastq(file_handle):
    """
    Generator object to parse a FASTQ file

    """
    name = "dummy"
    while name != "":
        name = file_handle.readline().strip()
        seq = file_handle.readline().strip()
        strand = file_handle.readline().strip()
        qual = file_handle.readline().strip()

        yield {"name": name, "strand": strand, "seq": seq, "qual": qual}
    return

def library(args):
    """
    Sequence generator iterator

    """
    if not args:
        yield ""
        return
    for i in args[0]:
        for tmp in library(args[1:]):
            yield i + tmp
    return

def atacBam2bed(filename, out, CB, UMI, noDup, num_threads):
    sample=filename.split('/')[-1].replace('.bam','')

    if sys.platform == 'darwin': # Mac OSX has BSD sed
        switch = '-E'
    else:
        switch = '-r'

    if not CB:
        # Put the sample name in the barcode slot
        if noDup:
            os.system('bamToBed -i %s -bedpe | awk -F ["\t":] \'{OFS="\t"}{print $1,$2,$6,"%s"}\' | sed %s \'s/^chr//g\' | awk \'!x[$0]++\' | gzip -c > %s_scTEtmp/o1/%s.bed.gz' % (filename, sample,switch, out, out))
        else:
            os.system('bamToBed -i %s -bedpe | awk -F ["\t":] \'{OFS="\t"}{print $1,$2,$6,"%s"}\' | sed %s \'s/^chr//g\' | gzip -c > %s_scTEtmp/o1/%s.bed.gz' % (filename, sample,switch, out, out))
    else:
        if noDup:
            os.system('bamToBed -i %s -bedpe | awk -F "\t" \'{OFS="\t"}{split($7, cb, "@"); print $1,$2,$6,cb[2]}\'  | sed %s \'s/^chr//g\' | awk \'!x[$0]++\' | gzip -c > %s_scTEtmp/o1/%s.bed.gz' % (filename, switch, out, out))
#             os.system('bamToBed -i %s  -bedpe | awk -F ["\t":] \'{OFS="\t"}{print $1,$2,$3,$4}\'  | sed %s \'s/^chr//g\' | awk \'!x[$0]++\' | gzip -c > %s_scTEtmp/o1/%s.bed.gz' % (filename, switch, out, out))
        else:
            os.system('bamToBed -i %s -bedpe | awk -F "\t" \'{OFS="\t"}{split($7, cb, "@"); print $1,$2,$6,cb[2]}\'  | sed %s \'s/^chr//g\' | gzip -c > %s_scTEtmp/o1/%s.bed.gz' % (filename, switch, out, out))

def para_atacBam2bed(filename, CB, out, noDup):
    if not os.path.exists('%ss_scTEtmp/o0'%out):
        os.system('mkdir -p %s_scTEtmp/o0'%out)

    sample=filename.split('/')[-1].replace('.bam','')

    if sys.platform == 'darwin': # Mac OSX has BSD sed
        switch = '-E'
    else:
        switch = '-r'

    if not CB:
        if noDup:
            os.system('bamToBed -i %s -bedpe | awk -F ["\t":] \'{OFS="\t"}{print $1,$2,$6,"%s"}\' | sed %s \'s/^chr//g\' | awk \'!x[$0]++\' | gzip -c > %s_scTEtmp/o0/%s.bed.gz' %(filename, sample, switch, out, sample))
        else:
            os.system('bamToBed -i %s -bedpe | awk -F ["\t":] \'{OFS="\t"}{print $1,$2,$6,"%s"}\' | sed %s \'s/^chr//g\' | gzip -c > %s_scTEtmp/o0/%s.bed.gz' %(filename, sample, switch, out, sample))
    else:
        if noDup:
#             os.system('bamToBed -i %s -bedpe | awk -F ["\t":] \'{OFS="\t"}{print $1,$2,$6,$7}\' | sed %s \'s/^chr//g\' | awk \'!x[$0]++\' | gzip -c > %s_scTEtmp/o0/%s.bed.gz' % (filename, switch, out, out))
            os.system('bamToBed -i %s | awk -F ["\t":] \'{OFS="\t"}{print $1,$2,$3,$4}\'  | sed %s \'s/^chr//g\' | awk \'!x[$0]++\' | gzip -c > %s_scTEtmp/o1/%s.bed.gz' % (filename, switch, out, out))
        else:
            os.system('bamToBed -i %s -bedpe | awk -F ["\t":] \'{OFS="\t"}{print $1,$2,$6,$7}\' | sed %s \'s/^chr//g\' | gzip -c > %s_scTEtmp/o0/%s.bed.gz' % (filename, switch, out, out))

def load_expected_whitelist(filename, logger):
    """
    **Purpose**
        Load the expected whitelist and output a set

    """
    expected_whitelist = []
    oh = open(filename, 'rt')
    for line in oh:
        expected_whitelist.append(line.strip())
    oh.close()

    expected_whitelist = set(expected_whitelist)

    logger.info('Found {0:,} expected barcodes'.format(len(expected_whitelist)))

    return expected_whitelist

def build_barcode_dict(barcode_filename, save_whitelist=False, expected_whitelist=False,
    gzip_file=True, logger=False, ondisk=True):
    '''
    **Purposse**
        The BAM and the FASTQ are not guaranteed to be in the same order, so I need to make a look up for
        the read ID and the barcode

    **Arguments**
        barcode_filename (Required)

        save_whitelist (Optional, default=False)
            save out the whitelist of barcodes (i.e. the ones actually observed)\

            TODO: This should be checked against the expected whitelist, and 1bp Hamming corrected

    **Returns**
        A dict mapping <readid>: <barcode>
    '''
    assert barcode_filename, 'barcode_filename is required'

    if expected_whitelist:
        logger.info('Checking against the expected whitelist and correcting barcodes')
    else:
        logger.warning('Not checking the barcodes against an expected whitelist, barcodes will not be corrected')

    bad_barcodes = 0
    rescued_barcodes = 0

    if ondisk:
        tmpfilename = './tpm_{0:}_{1:}_{2:}.dbm'.format(barcode_filename, time.time(), random.randint(0, 10000))
        barcode_lookup = dbm.open(tmpfilename, 'n')
    else:
        tmpfilename = None
        barcode_lookup = {}

    if gzip_file:
        oh = gzip.open(barcode_filename, 'rt')
    else:
        oh = open(barcode_filename, 'rt')

    for idx, fq in enumerate(fastq(oh)):
        barcode = fq['seq']
        if 'N' in barcode: # Discard this barcode
            bad_barcodes += 1
            continue

        if expected_whitelist and barcode not in expected_whitelist:
            # barcode not in the whitelist
            # see if we can resuce it:
            rescued = False
            for mm in generate_mismatches(barcode):
                if mm in expected_whitelist:
                    barcode = mm # Corrected
                    rescued_barcodes += 1
                    rescued = True
                    break
            if not rescued:
                bad_barcodes += 1 # unrecoverable
                continue

        name = fq['name'].split(' ')[0].lstrip('@') # Any other types seen?
        barcode_lookup[name] = barcode

        if (idx+1) % 10000000 == 0:
            logger.info('Processed: {:,} barcode reads'.format(idx+1))
    oh.close()

    logger.info('Processed: {:,} barcode reads from the FASTQ'.format(idx+1))
    logger.info('Bad reads with no barcode {:,} reads'.format(bad_barcodes))
    logger.info('Rescued {:,} reads'.format(rescued_barcodes))
    logger.info('Found {:,} valid reads'.format(len(set(barcode_lookup.keys())), ))
    logger.info('Found {:,} valid barcodes'.format(len(set(barcode_lookup.values())), ))

    if save_whitelist:
        logger.info('Saved whitelist: {0}'.format(save_whitelist))
        oh = open(save_whitelist, 'wt')
        for k in sorted(set(barcode_lookup.values())):
            oh.write('%s\n' % (k))

    oh.close()

    return barcode_lookup, expected_whitelist, tmpfilename

def parse_cbc(infile, outfile, logger):
    op = outfile
    inbam = pysam.AlignmentFile(infile, 'rb')
    outfile = pysam.AlignmentFile(outfile, 'wb', template=inbam)

    not_paired = 0 # unpaired ATAC
    no_matching_barcode = 0 # No matching read:barcode pair
    pairs_too_far_apart = 0


    for idx, read in enumerate(inbam):
        if (idx+1) % 10000000 == 0:
            logger.info('Processed: {:,} reads'.format(idx+1))
            #break

        if not read.is_paired:
            not_paired += 1
            continue

        if read.query_alignment_length > 1000:
            pairs_too_far_apart += 1
            continue

        # UMI iterator
        #try:
        #    umi = umi_iterator.__next__()
        #except StopIteration:
        #    umi_iterator = library(["ACGT"] * 14)

        # Add the barcode:
        # See if the read is in the lookup:
        if read.has_tag('CB'):
            read.query_name = read.query_name + '@' + read.get_tag('CB')
            outfile.write(read)

        else:
            no_matching_barcode += 1
            continue

    inbam.close()
    outfile.close()

    logger.info('Processed {:,} reads from the BAM'.format(idx+1))
    logger.info('{:,} reads were unpaired'.format(not_paired+1))
    logger.info('{:,} read pairs were too far apart'.format(pairs_too_far_apart+1))
    logger.info('Matched {0:,} ({1:.1f}%) reads to a barcode'.format(idx - no_matching_barcode, (idx - no_matching_barcode) / idx * 100.0))
    logger.info('Save BAM ouput file: {0}'.format(op))
    return op

def parse_bam(infile, barcode_lookup, outfile, barcode_corrector, logger):
    """
    **Purpose**
        Parse the BAM file and insert the CR: and YR: tags
    """
    inbam = pysam.AlignmentFile(infile[0], 'rb')
    outfile = pysam.AlignmentFile(outfile, 'wb', template=inbam)

    #umi_iterator = library(["ACGT"] * 14)

    not_paired = 0 # unpaired ATAC
    no_matching_barcode = 0 # No matching read:barcode pair
    corrected_barcodes = 0
    pairs_too_far_apart = 0

    quick_lookup = {}

    for idx, read in enumerate(inbam):
        if (idx+1) % 10000000 == 0:
            logger.info('Processed: {:,} reads'.format(idx+1))
            #break

        if not read.is_paired:
            not_paired += 1
            continue

        if read.query_alignment_length > 1000:
            pairs_too_far_apart += 1
            continue

        # UMI iterator
        #try:
        #    umi = umi_iterator.__next__()
        #except StopIteration:
        #    umi_iterator = library(["ACGT"] * 14)

        # Add the barcode:
        # See if the read is in the lookup:
        if read.query_name in barcode_lookup:
            read.set_tags([('CR:Z', barcode_lookup[read.query_name]),])
        else:
            no_matching_barcode += 1
            continue

        # The BAM file is not garunteed to be in order, but the pairs should be pretty close, so I just need to check for the other pair on a simple lookup list
        # and only write out the pairs once I got two
        if read.query_name in quick_lookup: # I found it's pair
            outfile.write(read)
            outfile.write(quick_lookup[read.query_name])
            del quick_lookup[read.query_name]
        else:
            # no pair, store it for later
            quick_lookup[read.query_name] = read

    inbam.close()
    outfile.close()

    logger.info('Processed {:,} reads from the BAM'.format(idx+1))
    logger.info('{:,} reads were unpaired'.format(not_paired+1))
    logger.info('{:,} read pairs were too far apart'.format(pairs_too_far_apart+1))
    logger.info('Matched {0:,} ({1:.1f}%) reads to a barcode'.format(idx - no_matching_barcode, (idx - no_matching_barcode) / idx * 100.0))
    logger.info('Save BAM ouput file: {0}'.format(infile[0]))
    return
