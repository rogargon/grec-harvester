#!/usr/bin/env python
# -*- coding: utf8 -*-

from bs4 import BeautifulSoup

from rdflib.graph import ConjunctiveGraph
from rdflib import Namespace, URIRef, Literal, RDF, BNode
from rdflib.collection import Collection

import urllib2
import simplejson
import re
import math
import argparse
import unicodedata

#GLOBAL VARS
pub_base_uri = "http://www.diei.udl.cat"
uri_person = "person"
uri_pub = "pub"
swrc = "http://swrc.ontoware.org/ontology#"
DC = Namespace("http://purl.org/dc/elements/1.1/")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
UNI = Namespace("http://swrc.ontoware.org/ontology#")

#END GLOBAL VARS

# Create the RDF Graph
graph = ConjunctiveGraph()
graph.bind("dc", DC)
graph.bind("rdfs", RDFS)
graph.bind("uni", UNI)
# End create RDF Graph


def clean_pub_title(string):
    '''Clear de name for the dictionary keys'''
    if ":" in string:
        return string.strip()[:-1]
    return string.strip()


def remove_accents(s):
    '''Quits accents and language specific characters of a string'''
    return ''.join((c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn'))


def clean_href(string):
    '''Clean the javascript stuff from the given content of href property of an anchor'''
    return string.split("'")[1]


def get_soup_from_url(url):
    '''Return a BS4 object from a given URL'''
    return BeautifulSoup(urllib2.urlopen(url), "lxml", from_encoding="UTF8")


def get_links_in_row(soup, rowname):
    '''Get a list of links from a BS4 object and a row name'''
    print u"Filtering data by row name: "+ rowname
    fila_pubs = soup.find("td", text=re.compile("^"+ rowname +"$")).find_parent("tr")
    link_list = [a["href"] for a in fila_pubs.find_all("a")]
    return link_list


def htmlize_string(string):
    '''Make a HTML valid string (quits spaces, commas, dots and accents or language specific characters)'''
    return remove_accents(string.replace(",", "").replace(".", "").replace(" ", ""))


def normalize_author_name(name):
    '''Normalize an author name to the form "Lastname, F."'''
    # Copied and translated to python from the file PubsRDFizer.java at lines 344 to 414 from rogargon (Roberto García)
    # https://github.com/rogargon/GRECRDFizer/blob/master/src/main/java/net/rhizomik/grecrdfizer/PubsRDFizer.java#L344
    if re.match(".*?(\S\S+)\s+(\S\S?)(?:\s+(\S))?$", name): # Process authornames like Smith J, Doe J R or Frost RA
        match = re.match(".*?(\S\S+)\s+(\S\S?)(?:\s+(\S))?$", name)
        name = match.group(1)+", "
        if None not in match.groups():
            name = name+match.group(2)+"."+match.group(3)+"."
        else:
            if len(match.group(2)) == 1:
                name = name +match.group(2)+"."
            else:
                name = name +match.group(2)[0]+"."+match.group(2)[1]+"."
    elif re.match("^(\S\S?)\s+(:?(\S)\s+)?(\S\S+)", name): # Process authornames like J Smith, J R Doe or RA Frost
        match = re.match("^(\S\S?)\s+(:?(\S)\s+)?(\S\S+)", name)
        name = match.group(4)+", "
        if None not in match.groups():
            name = name+match.group(1)+"."+match.group(3)+"."
        else:
            if len(match.group(1)) == 1:
                name = name +match.group(1)+"."
            else:
                name = name +match.group(1)[0]+"."+match.group(1)[1]+"."
    elif re.match("^(\S+)\s+(:?(\S+)\s+)?(\S+)", name): # Process authornames like John Smith or Ralph Albert Frost
        if name.isupper():
            name_list = name.split(" ")
            if len(name_list) == 4 or len(name_list) == 5:
                name = name_list[2].capitalize()+", "+name_list[0][0]+"."+name_list[1][0]+"."
            if len(name_list) == 3 or len(name_list) == 2:
                name = name_list[1].capitalize()+", "+name_list[0][0]
        else:
            match = re.match("^(\S+)\s+(:?(\S+)\s+)?(\S+)", name)
            name = match.group(1)[0]+"."
            if None not in match.groups():
                name = match.group(4)+", "+name+match.group(3)[0]+"."
            else:
                name = match.group(4)+", "+name
    #graph.add((URIRef(pub_base_uri+"/"+uri_person+"/"+htmlize_string(name)), DC.author, Literal(name)))
    return name


def normalize_author_list(string):
    '''Normalize an author list to the form "Lastname, F."'''
    if ";" in string:
        stringn = re.split(";| and | i | amb | y ", string)
    elif "," in string:
        if re.match("(\S\S+)\s+(\S\S?)(?:\s+(\S))?$", string.replace(".", " ").replace(",", " ").strip()):
            stringn = re.split(" and | amb | y ", string.replace(".", " ").replace(",", " ").strip())
        else:
            stringn = re.split(",| and | i | amb | y ", string)
    else:
        stringn = re.split(" and | amb | y ", string)
    author_list = [nom.replace(".", " ").replace(",", " ").strip() for nom in stringn]
    final_author_list = []
    for name in author_list:
        final_author_list.append(normalize_author_name(name))
    return final_author_list


def get_pubs_quantity(soup):
    '''Get the number of publications and pages in a BS4 object'''
    max_posts = int(soup.find("p", {"class": "consultac"}).text.split(":")[1].strip())
    posts_per_page = len(soup.find_all("p", {"class": "llista"}))
    max_pages = int(math.ceil(max_posts / float(posts_per_page)))
    return max_posts, max_pages


def rdfize_journal_article(pub_dict):
    pub_uriref = URIRef(pub_base_uri+"/"+uri_pub+"/"+pub_dict["Id. GREC"])

    graph.add((pub_uriref, RDF.type, UNI.Article))
    graph.add((pub_uriref, DC.year, Literal(pub_dict[u"Any"])))
    graph.add((pub_uriref, DC.title, Literal(pub_dict[u"Títol"])))
    graph.add((pub_uriref, UNI.authors, Literal("; ".join(pub_dict[u"Autors"]))))

    if pub_dict["ISSN"] != "":
        journal_uriref = URIRef(pub_base_uri+"/journal/"+pub_dict["ISSN"])
        graph.add((pub_uriref, UNI.isPartOf, journal_uriref))
        graph.add((journal_uriref, RDF.type, UNI.Journal))
        graph.add((journal_uriref, RDFS.label, Literal(pub_dict["Revista"])))
        graph.add((journal_uriref, UNI.ISSN, Literal(pub_dict["ISSN"])))

    if pub_dict[u"Pàgina inicial"] != "" or pub_dict[u"Pàgina final"] != "":
        graph.add((pub_uriref, UNI.pages, Literal(pub_dict[u"Pàgina inicial"] +"-"+ pub_dict[u"Pàgina final"])))
    if pub_dict["Volum"] != "":
        graph.add((pub_uriref, UNI.volume, Literal(pub_dict["Volum"])))

    for autor in pub_dict[u"Autors"]:
        autor_uriref = URIRef(pub_base_uri+"/"+uri_person+"/"+htmlize_string(autor))
        graph.add((pub_uriref, DC.author, autor_uriref))
        graph.add((autor_uriref, RDFS.label, Literal(autor)))


def rdfize_book_article(pub_dict):
    pub_uriref = URIRef(pub_base_uri+"/"+uri_pub+"/"+pub_dict["Id. GREC"])

    graph.add((pub_uriref, RDF.type, UNI.Article))
    graph.add((pub_uriref, DC.title, Literal(pub_dict[u"Títol"])))
    graph.add((pub_uriref, DC.title, Literal(pub_dict[u"Any"])))
    graph.add((pub_uriref, UNI.authors, Literal("; ".join(pub_dict[u"Autors"]))))

    if pub_dict[u"Pàgina inicial"] != "" or pub_dict[u"Pàgina final"] != "":
        graph.add((pub_uriref, UNI.pages, Literal(pub_dict[u"Pàgina inicial"] +"-"+ pub_dict[u"Pàgina final"])))
    if pub_dict["Volum"] != "":
        graph.add((pub_uriref, UNI.volume, Literal(pub_dict["Volum"])))

    for autor in pub_dict[u"Autors"]:
        autor_uriref = URIRef(pub_base_uri+"/"+uri_person+"/"+htmlize_string(autor))
        graph.add((pub_uriref, DC.author, autor_uriref))
        graph.add((autor_uriref, RDFS.label, Literal(autor)))

    if pub_dict["ISBN"] != "":
        book_uriref = URIRef(pub_base_uri+"/book/"+pub_dict["ISBN"])
        graph.add((pub_uriref, UNI.isPartOf, book_uriref))
        graph.add((book_uriref, RDF.type, UNI.Book))
        if pub_dict[u"Referència"] != "":
            graph.add((book_uriref, RDFS.label, Literal(pub_dict[u"Referència"])))
        graph.add((book_uriref, UNI.ISBN, Literal(pub_dict["ISBN"])))
        if pub_dict[u"Editorial"] != "": 
            graph.add((book_uriref, UNI.editor, Literal(pub_dict[u"Editorial"])))


def rdfize_thesis(pub_dict):
    pub_uriref = URIRef(pub_base_uri+"/"+uri_pub+"/"+pub_dict["Id. GREC"])

    graph.add((pub_uriref, RDF.type, UNI.Thesis))
    for autor in pub_dict[u"Autor"]:
        autor_uriref = URIRef(pub_base_uri+"/"+uri_person+"/"+htmlize_string(autor))
        graph.add((pub_uriref, DC.author, autor_uriref))
        graph.add((autor_uriref, RDFS.label, Literal(autor)))

    for director in pub_dict[u"Director"]:
        director_uriref = URIRef(pub_base_uri+"/"+uri_person+"/"+htmlize_string(director))
        graph.add((pub_uriref, UNI.supervisor, director_uriref))
        graph.add((director_uriref, RDFS.label, Literal(director)))


    graph.add((pub_uriref, DC.title, Literal(pub_dict[u"Títol"])))
    graph.add((pub_uriref, DC.year, Literal(pub_dict[u"Any"])))
    graph.add((pub_uriref, UNI.school, Literal(pub_dict[u"Facultat"])))
    graph.add((pub_uriref, DC.University, Literal(pub_dict[u"Universitat"])))


def rdfize_congress_paper(pub_dict):
    pub_uriref = URIRef(pub_base_uri+"/"+uri_pub+"/"+pub_dict["Id. GREC"])

    graph.add((pub_uriref, RDF.type, UNI.Article))
    for autor in pub_dict[u"Autors"]:
        autor_uriref = URIRef(pub_base_uri+"/"+uri_person+"/"+htmlize_string(autor))
        graph.add((pub_uriref, DC.author, autor_uriref))
        graph.add((autor_uriref, RDFS.label, Literal(autor)))

    graph.add((pub_uriref, DC.title, Literal(pub_dict[u"Títol"])))
    graph.add((pub_uriref, DC.year, Literal(pub_dict[u"Any"])))
    graph.add((pub_uriref, UNI.authors, Literal("; ".join(pub_dict[u"Autors"]))))
    graph.add((pub_uriref, UNI.Meeting, Literal(pub_dict[u"Congrés"])))


def rdfize_research_project(pub_dict):
    pass


def rdfize_european_project(pub_dict):
    pass


def rdfize_contract(pub_dict):
    pass


def rdfize_pub_list(pub_list):
    '''Translate the publication list structure to a RDF Graph structure'''
    for pub_dict in pub_list:
        if pub_dict.has_key(u"ISSN"):
            rdfize_journal_article(pub_dict)
        elif pub_dict.has_key(u"ISBN"):
            rdfize_book_article(pub_dict)
        elif pub_dict.has_key(u"Qualificació"):
            rdfize_thesis(pub_dict)
        elif pub_dict.has_key(u"Congrés"):
            rdfize_congress_paper(pub_dict)
        elif pub_dict.has_key(u"Unesco"):
            rdfize_research_project(pub_dict)
        elif pub_dict.has_key(u"Codi UE"):
            rdfize_european_project(pub_dict)
        else:
            rdfize_contract(pub_dict)
    return graph.serialize(format="pretty-xml")
    

def get_publication_dict(pub_url):
    '''Put all the publication info into a Python Dictionary where the keys are the fields'''
    pub_url = get_soup_from_url(pub_url)
    pub_data = pub_url.find_all("b")
    pub_dict = {}
    for item in pub_data:
        if len(item.next_element) < 25:
            titol = clean_pub_title(item.next_element)
            try:
                if titol == "Autors" or titol == "Autor" or titol == "Director":
                    pub_dict[titol] = normalize_author_list(item.next_element.next_element.strip())
                elif titol == "Nom" or clean_pub_title(item.next_element) == "Organisme":
                    pub_dict[titol] = item.parent.parent.find_all("td")[1].next_element
                elif titol == "Equip investigador":
                    res_list = [normalize_author_name(nom.next_element.strip()) for nom in item.parent.find_all("a", {"class":"inves"})]
                    pub_dict["Investigador principal"] = res_list[0]
                    pub_dict["Investigadors secundaris"] = res_list[1:]
                else:
                    pub_dict[titol] = item.next_element.next_element.strip()
            except:
                pub_dict[titol] = ""
    return pub_dict


def get_pub_list_from_link(link):
    '''Retrieve all the publications from a URL'''
    max_posts, max_pages = get_pubs_quantity(get_soup_from_url(link))
    link = link+"&PAG=1"
    publication_list = []
    print str(max_pages)+u" pages and "+str(max_posts)+u" pubs. found"

    for page in range(1, max_pages+1):
        print u"Getting data from page "+ str(page)
        link = link.replace(re.findall("&PAG=.*", link).pop(), "&PAG="+ str(page))
        pub_page = get_soup_from_url(link)
        for pub in pub_page.find_all("p", {"class": "llista"}):
            publication_list.append(get_publication_dict(clean_href(pub.find("a")["href"])))
    return publication_list


def get_all_pubs_from_link_list(link_list):
    '''Retrieve all the publications from a URL list'''
    publication_list = []
    for link in link_list:
        print u"Getting data from", link
        pub_page = get_soup_from_url(link)
        publication_list.extend(get_pub_list_from_link(link))
    return publication_list


def get_pubs_by_row_name(row_name):
    '''Retrieve all the publications by the row title'''
    url_obj = u'http://webgrec.udl.es/cgi-bin/DADREC/crcx1.cgi?PID=312186&IDI=CAT&FONT=3&QUE=CRXD&CRXDCODI=1605&CONSULTA=Fer+la+consulta'
    print "Getting DIEI data from GREC website"
    soup = get_soup_from_url(url_obj)
    link_list = get_links_in_row(soup, row_name)
    return get_all_pubs_from_link_list(link_list)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Little script for scraping data on DIEI GREC website")
    parser.add_argument("rowtitle",
        metavar = "\"title\"",
        help = "The row title (list) that you want to scrap data",
        type = str,
        nargs = "+")
    parser.add_argument("-t","--type",
        help="Type of the output for de harvested data",
        type=str,
        default="rdf",
        choices=["rdf", "json"])
    parser.add_argument("-f", "--file",
        help="Name of the file where the output will be written",
        type=str,
        required=True)
    args = parser.parse_args()

    for row_title in args.rowtitle:
        pubs = get_pubs_by_row_name(row_title)
        f = open(args.file, "w")
        if args.type == "json":
            f.write(simplejson.dumps(pubs, ensure_ascii = False).encode("utf8"))
        else:        
            f.write(rdfize_pub_list(pubs))
        print "Output written in "+ f.name
        f.close()