#!/usr/bin/env python
import sys
import pandas as ps
import tarfile
import StringIO
import warnings
warnings.filterwarnings("ignore", category=FutureWarning) 
#ignore the following warning; this piece of code needs to be adjusted in a future version of traitar
#/home/aaron/traitar/traitar/hmm2gff.py:226: FutureWarning: sort(columns=....) is deprecated, use sort_values(by=.....)
#  out_table_df.sort(columns = ["Phenotype", "cor"], ascending = [True, False]).to_csv("%s/%s.dat" % (out_gff_dir, sample), sep = "\t")
""" produce gff file from a hmmer hit file """

def get_protein_acc(fasta_id):
    """extract from a fasta id like gi|17233466|ref|NP_490586.1| the protein accession NP_490586.1"""
    return fasta_id.split("|")[3]
    #return "_".join(fasta_id.split("|")[1].split("_")[3:5])


def read_rel_feats(model_tar, pts):
    """read in pfams relevant for all predicted phenotypes"""
    #pfam to phenotype mapping
    pf2pt = {}
    #store relevant pfam lists
    rel_feat_list = []
    #extract pfam lists
    for pt in pts:
        rel_feat_list.append(model_tar.extractfile("%s_majority_features+weights.txt" % pt))
    #process pfam lists
    for i in range(len(rel_feat_list)): 
        pfs = ps.read_csv(rel_feat_list[i], sep = "\t", index_col = 0)
        for pf in pfs.index:
            if not pf in pf2pt:
                if not type(pfs.loc[pf, "Pfam_acc"]) == type(ps.Series()):
                    pf2pt[pfs.loc[pf, "Pfam_acc"]] = [(pts[i], pfs.loc[pf, "cor"])]
                else: 
                    print pf, pts[i]
                    print pfs.loc[pf, "Pfam_acc"]
            else:
                if not pt in pf2pt[pf]:
                    pf2pt[pf].append(pts[i])
    return pf2pt


def read_gff(gff_file, mode):
    """read a gene calling gff"""
    f = open(gff_file)
    gene_dict = {}
    i = 0
    fasta = False
    for l in f:
        i += 1
        # print i
        if l.startswith("#") or l.startswith("\n"):
            continue
        else:
            if mode == "metagenemark":
                read_genemark_entry(l, gene_dict)
            elif mode == "prodigal":
                read_prodigal_entry(l, gene_dict)
            elif mode == "ncbi":
                read_ncbi_entry(l, gene_dict)
            elif mode == "refseq":
                read_refseq_entry(l, gene_dict)
            elif mode == "img":
                read_img_entry(l, gene_dict)
            elif mode == "genbank":
                #in genbank gene gffs the original nucleotide sequence can be appended to the gff"
                if l.startswith(">"):
                    fasta = True 
                    continue
                if fasta and l.startswith(('a','g', 'c', 't')):
                    continue
                else:
                    fasta = False
                read_genbank_entry(l, gene_dict)
    f.close()
    return gene_dict


def read_genemark_entry(l, gene_dict):
    """read and parse one line from a genemark gff"""
    elems = l.strip().split("\t")
    gene_dict[
        elems[8].split(" ")[0].strip(",").replace("=", "_")] = (
        elems[0].split(" ")[0], int(
            elems[3]), int(
            elems[4]), elems[6])

def read_prodigal_entry(l, gene_dict):
    """read and parse one line from a prodigal gff"""
    elems = l.strip().split("\t")
    #print elems[8].split(";"), len(elems)
    attrs = dict(
        [(i.split("=")[0], i.split("=")[1])
        for i in elems[8].strip(";").split(";")])
    gene_dict["%s_%s"% (elems[0], attrs["ID"].split("_")[1])] = (
            elems[0], int(
                elems[3]), int(
                elems[4]), elems[6])

def read_img_entry(l, gene_dict):
    """read and parse one line from an IMG gff"""
    elems = l.strip().split("\t")
    if elems[2] == "CDS":
        try:
            attrs = dict(
                [(i.split("=")[0], i.split("=")[1]) for i in elems[8].strip(";").split(";")])
        except IndexError:
            sys.stderr.write("something went wrong in line; skipping \n%s\n" % l)
            return 
        gene_dict[attrs["ID"]] = (
            elems[0], int(
                elems[3]), int(
                elems[4]), elems[6])


def read_ncbi_entry(l, gene_dict):
    """read and parse one line from a ncbi gff"""
    elems = l.strip().split("\t")
    if elems[2] == "CDS":
        attrs = dict(
            [(i.split("=")[0], i.split("=")[1])
             for i in elems[8].split(";")])
        gene_dict[
            attrs["Name"]] = (
            elems[0], int(
                elems[3]), int(
                elems[4]), elems[6])

def read_refseq_entry(l, gene_dict):
    """read and parse one line from a refseq gff"""
    elems = l.strip().split("\t")
    if elems[2] == "CDS":
        attrs = dict(
            [(i.split("=")[0], i.split("=")[1])
             for i in elems[8].split(";")])
        gene_dict[
            attrs["ID"]] = (
            elems[0], int(
                elems[3]), int(
                elems[4]), elems[6])

def read_genbank_entry(l, gene_dict):
    """read and parse one line from a genbank gff"""
    elems = l.strip().split("\t")
    if elems[2] == "CDS":
        attrs = dict(
            [(i.split("=")[0], i.split("=")[1])
             for i in elems[8].split(";")])
        gene_dict[
            attrs["locus_tag"]] = (
            elems[0], int(
                elems[3]), int(
                elems[4]), elems[6])



def get_coords(gene_start, gene_end, ali_from, ali_to, strand):
    n_start = ali_from * 3 - 2
    n_end = ali_to * 3 - 2
    # if strand == "+":
    return (gene_start + n_start, gene_start + n_end)
    # else:
    #    return (gene_end - n_end, gene_end  - n_start)


def write_hmm_gff(hmmer_file, out_gff_dir, gene_dict, sample, skip_genes, mode,  model_tar, predicted_phenotypes, description = False):
    #read in pfam accession to description mapping
    if description:
        pfam_pts_mapping_f = "pfam_pts_names_nl_desc.txt"
        acc2desc = ps.read_csv(model_tar.extractfile(pfam_pts_mapping_f), header=None, index_col = 1, sep = "\t") 
        acc2desc.iloc[:, 0] = acc2desc.iloc[:, 0] - 1
        id2desc = ps.read_csv(model_tar.extractfile(pfam_pts_mapping_f), header=None, index_col = 0, sep = "\t") 
        id2desc.index = id2desc.index.values - 1 
    out_table = []
    with open(hmmer_file, 'r') as hmmer_fo:
        # skip param line and header
        hmmer_fo.readline()
        hmmer_fo.readline()
        hmmer_fo.readline()
        rel_feats_dict = None
        # read in relevant which shall be highlighted
        pts = predicted_phenotypes.split(",") 
        if pts is not None:
            pf2pt = read_rel_feats(model_tar, pts)
        #print rel_feats_dict
        # open global output table
        # open out gffs for reading
        out_gffs = dict([(i, open("%s/%s_%s.gff"%(out_gff_dir, sample, id2desc.loc[int(i),].iloc[0].replace(" ", "_").replace("(", "_").replace("(", "_")), 'w')) for i in pts])
        out_gffs["Pfams"] = open("%s/%s_Pfams.gff" %(out_gff_dir, sample), 'w')
        #gff heade, r
        for i in out_gffs:
            out_gffs[i].write("""##gff-version 3\n""")
        for l in hmmer_fo:
            elems = l.strip().split("\t")
            # change pfam accession PF00001.3 into PF00001
            gid, acc, name, ali_from, ali_to, ieval = [
                get_protein_acc(elems[0]) if mode == "ncbi" or mode == "refseq" else elems[0], elems[4].split(".")[0], elems[3], int(elems[17]), int(elems[18]), elems[11]]

            if gid not in gene_dict:
                if not skip_genes:
                    print >> sys.stderr, gid, "not found in input orf gff file"
                    if mode == "ncbi":
                        print >> sys.stderr, "entry might be outdated, skipping"
                        continue
                    if mode == "img":
                        print >> sys.stderr, "might be a semicolon ; delimiter within an attribute; sample is %s\n" % sample
                        continue
                else:
                    continue
            contig_name, gene_start, gene_end, strand = gene_dict[gid]
            hmm_coords = get_coords(gene_start, gene_end, ali_from, ali_to, strand)
            colour = ""
            # check if this feature is among the highest ranking features and add
            # colour and rank if so 
            #print acc, rel_f
            description_string = ""
            if description and acc in acc2desc.index:
                description_string = ";Description=%s" % (acc2desc.loc[acc,].iloc[1])
            gff_line = "%s\tHMMER\tPfam\t%s\t%s\t%s\t%s\t.\tParent=%s;Name=%s;Note=%s%s%s\n" %(contig_name, hmm_coords[0], hmm_coords[1], ieval, strand, gid, acc, name, description_string, colour)
            out_gffs["Pfams"].write(gff_line)
            if pf2pt is None or acc in pf2pt:
                #if not rel_feats_dict is None:
                #    colour = ";colour=3;rank=%s" % (rel_feats_dict[acc])
                for i in pf2pt[acc]:
                    out_gffs[i[0]].write(gff_line)
                    out_table.append("%s\t%s\t%s\t%s\t%s\n" %(id2desc.loc[int(i[0]),].iloc[0], gid, acc, acc2desc.loc[acc,].iloc[1], i[1]))
    out_table_df = ps.read_csv(StringIO.StringIO("".join(out_table)), sep = "\t", header = None)
    out_table_df.columns = ["Phenotype", "gene_id", "Pfam_acc", "Pfam_description", "cor"]
    out_table_df.sort(columns = ["Phenotype", "cor"], ascending = [True, False]).to_csv("%s/%s.dat" % (out_gff_dir, sample), sep = "\t")
    #close out gffs
    for i in out_gffs:
        out_gffs[i].close()

# extract the information from the hmmer hit file which goes into the
# output gff file and extract the original position in the genome/contig
def run(in_file, out_gff_f, gene_gff_f, sample, gene_gff_mode, model_tar, predicted_pts = None):
    gene_dict = read_gff(gene_gff_f, gene_gff_mode)
    #print gene_dict
    write_hmm_gff(in_file, out_gff_f, gene_dict, sample, False, gene_gff_mode, model_tar, predicted_pts, True)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser("predict phenotypes from hmmer Pfam annotation")
    parser.add_argument("input_hmm", help= 'input HMMer file')
    parser.add_argument("gene_gff", help= 'gene prediction gff file')
    parser.add_argument("output_gff_dir", help= 'output GFF file')
    parser.add_argument("sample", help= 'sample file')
    parser.add_argument("gene_gff_mode", choices = ["img", "prodigal", "ncbi", "refseq", "metagenemark", "genbank"], help= "origin of the gene prediction (Prodigal, NCBI, metagenemark)")
    parser.add_argument("model_tar", help = "tar.gz file with relevant features etc.")
    parser.add_argument("--predicted_pts", "-r", help='file with some relevant annotation features', default = None)
    args = parser.parse_args()
    model_tar =  tarfile.open(args.model_tar)
    run(args.input_hmm, args.output_gff_dir, args.gene_gff, args.sample, args.gene_gff_mode,  model_tar, args.predicted_pts)
    model_tar.close()
