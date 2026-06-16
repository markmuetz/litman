Citation searching
==================

I have tried to work out what I can use to to citation searching, to e.g. generate a list of DOIs
from titles. What I would love is to be able to generate a
[citation graph](https://en.wikipedia.org/wiki/Citation_graph) of all my papers. This is proving to
be quite tricky.

There are a few options for getting DOIs:

Google scholar
--------------

Works, but there is no public API, it would be down to scraping plus probably being banned from the
service. Not sure I could get cited-by/cites info from it either.

Cross ref
---------

This can go from a title to a DOI, but not much else. They must have an internal cited-by database,
but it doesn't seem to be publicly available. Has an API (with Python client): https://search.crossref.org/help/api
Can get cited-by counts, but not actual DOIs.

Mendeley
--------

Similar to cross ref. Has an API (with Python client): https://dev.mendeley.com/

Scopus
------

This looks promising: https://dev.elsevier.com/documentation/AbstractCitationAPI.wadl
I have not been able to access this API though. Perhaps I need to set up my keys in a different way.


Microsoft Academic Graph
------------------------

Looks promising: see e.g.
https://docs.microsoft.com/en-us/azure/cognitive-services/Academic-Knowledge/graphsearchmethod.

Each retrieved entry comes with an RId field of cited papers (MAG ids). (normally, but some, e.g.
RKW1988, don't have this field.) You can also access cited-by papers by doing a search on RId. See
`mag_client` and `mag_cited_by` commands.

Struggled to get started using API:
https://stackoverflow.com/questions/50896049/getting-started-using-microsoft-academic-graph-api
Fix suggested there works.

Noticed a problem with one of their entries (AS74!):
https://twitter.com/markmuetz/status/1009076218338127872.

Others
------

* Web of science
* CiteSeerX

Update 2026-06-16
-----------------

Microsoft Academic Graph was retired by Microsoft at the end of 2021, so the MAG-based
code (`mag-search`, `mag-cited-by`, `mag_client`, and the dot/citation-graph scripts that
depended on it) has been ripped out.

The direct successor is [OpenAlex](https://openalex.org/) (https://docs.openalex.org/), an
open catalogue built on the MAG data model. It is free, needs no API key (a "polite pool"
just asks for an email in the request), and exposes works, DOIs, and both `referenced_works`
(cites) and a cited-by query (`filter=cites:<id>`) — i.e. everything the old MAG code used
for the citation-graph idea. If I ever want to revive citation searching, OpenAlex is the
target to port to.
