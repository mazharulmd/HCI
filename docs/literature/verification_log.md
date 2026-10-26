# Reference verification log (26 Oct 2026)

Every entry of `paper/references.bib` was matched to an external record. Two
channels were available from the sandbox: **C** = Consensus record (Semantic
Scholar / OpenAlex metadata: title, authors, year, venue); **W** = web search
result pointing to a publisher page, arXiv listing or institutional
repository. Direct OpenAlex / Crossref / arXiv API access was blocked (HTTP
403), so the automated `verify_bibtex` tool returned "unchecked" and could
not be used.

Policy: authors are listed in full only where the record showed the full list;
otherwise `and others`. arXiv identifiers and DOIs are kept only where seen in
a record.

| Key | Channel | Notes |
|---|---|---|
| perez2022ignore | W | arXiv 2211.09527; NeurIPS 2022 ML Safety Workshop |
| greshake2023not | C | AISec 2023 |
| liu2023houyi | C | arXiv |
| liu2024formalizing | W | USENIX Security 2024, pp. 1831-1847 |
| zhan2024injecagent | C | Findings ACL 2024 (venue from authors' release; record lists arXiv) |
| debenedetti2024agentdojo | C | NeurIPS 2024 D&B |
| yi2025bipia | C | KDD 2025 |
| zhang2025asb | W | ICLR 2025 proceedings page |
| zhan2025adaptive | C | record title/authors; venue Findings NAACL 2025 |
| abdelnabi2026always | C+W | arXiv 2605.17634 |
| ma2026autodojo | C | |
| hofer2026automated | C | |
| chen2026autoinject | C | |
| pandya2025attention | C | |
| alizadeh2025simple | C | |
| wang2026landscape | C | |
| shaw2026silent | C | |
| khan2026evaluating | C | journal *Computers* |
| hines2024spotlighting | C | |
| chen2025struq | C | USENIX Security 2025 (as cited by Pandya 2025 record) |
| chen2025secalign | C | CCS 2025 |
| chen2025metasecalign | W | arXiv 2507.02735, authors from listing |
| wallace2024instruction | C | |
| shi2025promptarmor | C | |
| debenedetti2026camel | C | SaTML 2026 |
| wu2024fsecure | C | |
| costa2025fides | W | arXiv 2505.23643 |
| shi2025progent | C+W | arXiv 2504.11703 |
| zhu2025melon | C | ICML 2025 |
| jia2025taskshield | C | |
| an2025ipiguard | C | |
| beurerkellner2025patterns | C | |
| li2025drift | C | |
| kim2025pfi | C | |
| zhao2026clawguard | C | |
| he2026attriguard | C | |
| li2026toolfence | C | |
| narisetty2026adaptive | C | |
| garby2026llmbda | C | |
| gong2025csagent | C+W | arXiv 2509.22256 |
| zhu2025miniscope | C+W | arXiv 2512.11147 |
| michael2026permission | C+W | arXiv 2607.13718 |
| yan2026policies | C | N=113 user study |
| ge2026authorization | C | CHI 2026 Extended Abstracts |
| brigham2026janus | C | |
| wu2026permissions | C | IEEE S&P 2026 |
| salerno2026agent | C | |
| south2025delegation | C | |
| su2026riskcards | C | *International Journal of Graphic Design* |
| mozannar2025magentic | W | arXiv 2507.22358 |
| he2025plan | W | CHI 2025, DOI 10.1145/3706598.3713218 |
| amershi2019guidelines | W | CHI 2019 |
| parasuraman1997humans | C | Human Factors |
| lee2004trust | C | Human Factors |
| bucinca2021trust | C | PACM HCI (CSCW1) 2021. The Consensus record lists the second author first; author order taken from the paper |
| vasconcelos2023explanations | C | PACM HCI (CSCW1); record year 2022 (preprint), published 2023 |
| bansal2021whole | W | CHI 2021, DOI 10.1145/3411764.3445717 |
| cranor2008framework | W | UPSEC 2008 |
| egelman2008warned | W | CHI 2008, pp. 1065-1074 |
| sunshine2009crying | W | USENIX Security 2009 |
| felt2012android | W | SOUPS 2012, DOI 10.1145/2335356.2335360 |
| akhawe2013alice | W | USENIX Security 2013 |
| anderson2015polymorphic | C | CHI 2015 |
| vance2018tuning | C | MIS Quarterly 2018 |
| vance2025fog | C | MIS Quarterly 2025 |
| hart1988nasatlx | W | Advances in Psychology 52, DOI 10.1016/S0166-4115(08)62386-9 |
| brooke1996sus | W | Usability Evaluation in Industry |
| jian2000trust | W | Int. J. Cognitive Ergonomics 4(1):53-71 |
| macmillan2005detection | W | 2nd edition. Year (2004/2005) differs across listings; 2005 is the commonly cited year |
| saltzer1975protection | W | Proc. IEEE 63(9):1278-1308 |
| denning1976lattice | W | CACM 19(5):236-243, DOI 10.1145/360051.360056 |
| hardy1988confused | W | ACM SIGOPS OSR 22(4) |
| nissenbaum2004privacy | W | Washington Law Review 79:119 (pagination varies across listings) |
