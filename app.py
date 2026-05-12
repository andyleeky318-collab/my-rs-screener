import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# 1. Setup Streamlit Page
st.set_page_config(page_title="Chrome Sector RS", layout="wide")
st.title("🚀 Chrome Sector Relative Strength")

# 2. Industry Database from Pine Script
INDUSTRIES = {
    "Nuclear": ["URA", "NLR", "CEG", "CCJ", "OKLO", "UUUU", "SMR"],
    "MAG7": ["AAPL", "GOOGL", "NVDA", "META", "MSFT", "AMZN", "TSLA"],
    "ETF": ["XLK", "XLF", "XLE", "XLP", "XLU", "XLI", "XLY", "XLV", "XLC", "XLB"],
    "SPACE": ["UFO", "VSAT", "ARKX", "PL", "RKLB", "ASTS"],
    "CATHIE WOOD": ["ARKG", "ARKK", "ARKQ", "ARKW", "ARKF", "ARKX"],
    "CHINA": ["FUTU", "LI", "KWEB", "XPEV", "NIO", "PDD", "BIDU", "JD", "BABA"],
    "DATA CENTER / AI HOSTING": ["WGMI", "CRWV", "NBIS", "IREN", "WULF", "CORZ", "CIFR", "HUT", "BTDR"],
    "ENERGY SOLAR": ["TAN", "SEDG", "ENPH", "FSLR", "ARRY", "SHLS", "CSIQ", "RUN", "NOVA"],
    "COML SVCS-ADVRTSNG": ["OMC", "IPG", "DJT"],
    "AEROSPACE/DEFENSE": ["ITA", "RTX", "LMT", "HON", "BA", "GD", "NOC", "TDG", "LHX", "HWM", "AXON", "HEI", "LDOS", "TDY", "TXT", "FTAI", "CW", "BWXT", "HII", "CR", "DRS", "LOAR", "AVAV", "HXL", "SPR", "KTOS", "MIR", "OSIS", "AIR", "MRCY"],
    "AGRICULTURAL OPRTIONS": ["ADM", "BG", "PPC", "CALM", "SEB"],
    "TRNSPRT-AIR FREIGHT": ["UPS", "FDX"],
    "TRANSPORTATION-SVCS": ["DASH", "EXPD", "CHRW", "CART", "GXO", "HUBG", "UBER", "PFGC", "SARO", "VNT", "VRRM", "CAAP"],
    "TRNSPRTTIN-AIRLNE": ["JETS", "DAL", "UAL", "LUV", "AAL", "ALK", "CPA", "SKYW"],
    "ENERGY-ALT/OTHER": ["BIP", "TLN", "CWEN", "AY", "NEP", "BEPC"],
    "MINING-METAL ORES": ["AA", "SCCO", "FCX", "CCJ", "CRS", "ATI", "MP", "TECK"],
    "APPAREL-SHOES & REL": ["NKE", "DECK", "ONON", "RL", "SKX", "BIRK", "CROX", "LEVI", "VFC", "GIL", "PVH", "COLM", "KTB", "SHOO"],
    "RETAIL-APPRL/SHOES/ACC": ["TJX", "ROST", "BURL", "TPR", "GAP", "ANF", "BBWI", "CPRI", "BOOT", "AEO", "URBN", "CRI", "BKE", "FL"],
    "AUTO/TRCK-ORGNL EQP": ["ITW", "CMI", "APTV", "ITT", "DCI", "ALSN", "ALV", "GNTX", "LEA", "BC", "ATMU", "VC", "BWA"],
    "AUTO/TRCK-RPLC PRTS": ["LKQ", "DORM", "AAP"],
    "BEVERAGES-ALCOHOLIC": ["STZ", "TAP", "SAM"],
    "BEV-NON-ALCOHOLIC": ["KO", "MNST", "CCEP", "COKE", "BRBR", "CELH", "FIZZ"],
    "MEDICAL-BIOMED/BTH": ["AMGN", "GILD", "MRNA", "ILMN", "SMMT", "PCVX", "BMRN", "TECH", "NUVL", "ELAN", "HALO", "BPMC", "RNA", "KRYS", "ADMA", "BBIO", "IMVT", "ACLX", "AXSM", "CRSP", "DNLI", "ALVO", "MRUS", "APGE", "DYN", "RYTM", "KYMR", "EWTX", "PTGX", "TWST", "SWTX", "TXG", "CGON", "JANX", "ARWR", "VERA", "NVAX", "CLDX"],
    "MEDIA-RADIO/TV": ["FOX", "SIRI", "PARA", "NXST", "TGNA"],
    "TELCOM-SVC-CBL/SAT": ["CMCSA", "CHTR"],
    "LEISRE-GAMNG/EQUIP": ["FLUT", "LVS", "MGM", "WYNN", "CZR", "LNW", "BYD", "IGT", "RSI", "DKNG", "CHDN", "PENN"],
    "CHEMICALS-AG": ["NTR", "CTVA", "CF", "MOS", "FMC", "SMG"],
    "CHEMICALS-BASIC": ["DD", "ESI", "AVNT", "HUN", "IOSP", "DOW", "LYB", "WLK", "AVTR", "CE", "EMN", "CC"],
    "CHEMICALS-SPECIALTY": ["LIN", "ECL", "APD", "ALB", "CHX", "CBT", "NEU", "KWR", "HWKN", "MTX", "TROX"],
    "ENERGY COAL": ["HCC", "BTU", "ARLP", "CEIX", "AMR", "ARCH"],
    "MEDIA-DIVERSIFIED": ["WMG", "EDR"],
    "COMPTER-NETWRKING": ["ANET", "JNPR", "CSCO", "CALX"],
    "COMPTR-DATA STRGE": ["DRAM", "WDC", "STX", "MU", "SNDK"],
    "CMP-HRDWRE/PERIP": ["DELL", "HPQ", "SMCI", "HPE", "ZBRA", "NATL"],
    "CONTAINERS/PACKAGING": ["SW", "BALL", "PKG", "AVY", "AMCR", "OC", "CCK", "ATR", "GPK", "SLGN", "SON", "SEE", "GEF", "PTVE", "OI", "BERY"],
    "OIL&GAS-DRILLING": ["SLB", "BKR", "NE", "VAL", "HP", "SDRL"],
    "BLDG-CMENT/CNCRT": ["CRH", "MLM", "VMC", "EXP", "SUM", "KNF", "USLM"],
    "CMPTER-TECH SRVCS": ["PAYX", "MSCI", "VRSK", "ZS", "TYL", "GDDY", "J", "FDS", "AKAM", "DBX", "EXLS", "KD", "MARA", "EEFT", "DXC", "CORZ", "AVPT", "ACN", "CTSH", "CDW", "CACI", "PSN", "EPAM", "DOX", "KBR", "GLOB", "NSIT", "SAIC", "ASGN"],
    "RETAIL-DPRTMNT STRS": ["DDS", "M", "JWN", "KSS"],
    "RETAIL-DISCNT&VARI": ["DG", "DLTR", "FIVE", "OLLI"],
    "RETAIL-DRUG STORES": ["CVS"],
    "UTILITY-ELCTRIC PWR": ["NEE", "SO", "CEG", "DUK", "AEP", "SRE", "D", "VST", "PEG", "PCG", "EXC", "XEL", "ED", "EIX", "WEC", "ETR", "DTE", "FE", "PPL", "AEE", "ES", "CMS", "NRG", "CNP", "LNT", "AGR", "EVRG", "AES", "PNW", "OGE", "IDA", "POR", "ORA", "BKH", "TXNM", "ALE", "NWE", "MGEE"],
    "ELECTRICAL POWER/EQPMT": ["ETN", "GEV", "AME", "ROK", "HUBB", "RRX", "GNRC", "AYI", "BDC", "ENS", "FLNC", "SMR", "ATKR", "PBW", "POWL", "BE", "ENVX"],
    "TELCOM-FIBR OPTCS": ["AAOI", "COHR", "CIEN", "FN", "LITE"],
    "ELEC-PARTS": ["APH", "GLW", "NVT", "CAMT", "TEL"],
    "ELEC-SCNTIFIC/MSRNG": ["PH", "EMR", "KEYS", "FTV", "CGNX", "NOVT", "ST", "NXT", "ITRI", "ESE", "SXI", "MTRN"],
    "ELEC-SEMICNDCTR EQP": ["ASML", "KLAC", "AMAT", "LRCX", "ONTO", "NVMI", "TER", "AEIS", "MKSI", "ENTG", "ACLS"],
    "ELEC-CONTRACT MFG": ["SOLS", "VRT", "FLEX", "PLXS", "JBL"],
    "ELEC-MISC PRODUCTS": ["OLED", "LFUS", "VSH"],
    "WHOLESALE-ELECT": ["SNX", "ARW", "AVT", "REZI"],
    "RETAIL-CNSMR ELEC": ["BBY", "GME"],
    "CONSUMER PROD-ELEC": ["SN", "ROKU", "WHR", "SPB", "AAPL"],
    "BLDG-HEAVY CONSTR": ["PWR", "EME", "FIX", "ACM", "TTEK", "MTZ", "APG", "FLR", "DY", "STRL", "ROAD", "GVA", "PRIM"],
    "BLDG-RSIDNT/COMML": ["BLD", "IBP", "EXPO", "IESC", "DHI", "LEN", "NVR", "PHM", "TOL", "MTH", "TMHC", "KBH", "SKY", "MHO", "TPH", "FTDR", "GRBK", "DFH", "CCS", "LGIH"],
    "BLDG-MBILE/MFG & RV": ["CVCO", "PATK"],
    "POLLUTION CONTROL": ["WM", "RSG", "CLH", "CWST", "SRCL"],
    "COMML SVCS-LEASING": ["URI", "AER", "UHAL", "WSC", "R", "AL", "HRI", "WD", "CAR", "MGRC", "PRG"],
    "FINANCE-CARD/PMTPR": ["AXP", "DFS", "SYF", "AFRM", "FCFS", "SLM", "V", "MA", "PYPL", "GPN", "CPAY", "FOUR", "WEX", "PAY", "RELY"],
    "FINANCE-CONS LOAN": ["RKT", "OMF", "ENVA", "NNI"],
    "FINANCE-CMRCL LOAN": ["COOP", "OBDC", "PFSI", "CACC"],
    "FINANCE-BLANK CHECK": ["AACT", "AAM", "BCSF", "BFAC", "EQV", "HYAC", "LOCL", "MNTN", "MSDL", "NCDL", "OKLO", "PHYT", "PSBD", "RCFA", "RMI", "RRAC", "SBXC", "SBXD", "SEDA", "WEL"],
    "FINANCIAL SVC-SPEC": ["BLK", "SPGI", "MCO", "EFX", "TRU", "ICLR", "BAH", "MEDP", "CRL", "FCN", "MMS", "CBZ", "NSP", "ICFI", "EVH", "FA"],
    "WHOLESALE-FOOD": ["SYY", "USFD"],
    "RETAIL-SPR/MINI MKTS": ["KR", "SFM", "ACI", "TBBB", "CASY"],
    "FOOD-PACKAGED": ["KHC", "GIS", "CAG", "SMPL", "MDLZ", "KDP", "HSY", "K", "CPB", "SJM", "POST", "LANC", "FLO", "NOMD", "UTZ", "THS"],
    "FOOD-MEAT PRODUCTS": ["TSN", "HRL"],
    "FOOD-MISC PREP": ["PEP", "IFF", "MKC", "LW", "INGR", "DAR", "BCPC", "ASH", "JJSF", "SXT", "TR"],
    "FOOD-CONFECTIONERY": ["FRPT", "BROS"],
    "BLDG-WOOD PRDS": ["UFPI", "LPX", "TREX"],
    "UTILITY-GAS DSTRIBTN": ["TRGP", "CQP", "ATO", "NI", "MDU", "BIPC", "SWX", "NJR", "OGS", "SR", "CPK", "EE"],
    "RTAIL-HME FRNSHNGS": ["TPX", "MBC", "WSM", "W", "RH"],
    "RETL WHSLE BLDG PRDS": ["HD", "LOW", "BLDR", "FND", "CNM", "BECN", "BCC", "GMS"],
    "MEDCAL-HOSPITALS": ["HCA", "THC", "UHS"],
    "MED-LONG-TRM CARE": ["CHE", "PACS", "SEM", "SGRY", "ARDT", "ENSG", "AMED", "ADUS"],
    "MEDICAL-SERVICES": ["DVA", "SOLV", "EHC", "ACHC", "RDNT", "OPCH", "HIMS", "GH", "BTSG", "CON", "AZTA"],
    "LEISURE-LODGING": ["MAR", "HLT", "RCL", "CCL", "VIK", "H", "NCLH", "MTN", "WH", "CHH", "RRR", "TNL", "VAC"],
    "COSMETICS/PERSNL CRE": ["PG", "CL", "KMB", "KVUE", "EL", "CHD", "CLX", "ELF", "IPAR"],
    "SOAP & CLNG PREPARAT": ["REYN", "ENR"],
    "DVRSIFIED OPRTIONS": ["MMM", "AGS", "HI", "RLX", "WMS", "AWI", "BRC", "YETI", "LCII"],
    "MCHNRY-GEN INDSTRL": ["GE", "TT", "CARR", "JCI", "IR", "XYL", "DOV", "LII", "PNR", "IEX", "GGG", "NDSN", "LECO", "WWD", "AAON", "FLS", "MIDD", "MOD", "WTS", "BMI", "ZWS", "ESAB", "TKR", "GTLS", "GTES", "FELE", "KAI", "MWA", "NPO", "JBT", "CXT", "OII", "SYM"],
    "CHEMICALS-PAINTS": ["SHW", "PPG", "RPM", "AXTA"],
    "CHEMICALS-SPECIALTY": ["CSWI", "OLN", "FUL", "WDFC", "AZZ", "UFPT"],
    "COMPTR SFTWR-SCRITY": ["BUG", "FTNT", "PANW", "CRWD", "CHKP", "RBRK", "RPD"],
    "COMPTR SFTWR-ENTR": ["IGV", "TWLO", "MSFT", "ORCL", "CRM", "IBM", "NOW", "ADP", "DOCN", "PLTR", "ADSK", "ROP", "TEAM", "SNOW", "VEEV", "HUBS", "PTC", "MDB", "MANH", "TOST", "MNDY", "WDAY", "SSNC", "GWRE", "BSY", "PEGA", "QTWO", "APPF", "BOX", "WK", "SQSP"],
    "COMPTER SFTWR-DSGN": ["ADBE", "INTU", "SNPS", "CDNS", "ANSS", "IOT", "DT", "TRMB", "WIX"],
    "CMPTR SFTWR-FINCL": ["FICO", "FIS", "SQ", "NU", "SHOP"],
    "CMP SFTWR-GAMING": ["EA", "TTWO", "RBLX"],
    "CMP SFTWR-DBASE": ["DDOG"],
    "COMPTR SFTWR-DSKTP": ["ZM", "SNAP", "Z"],
    "CMPTR SFTWR-MDCL": ["APP", "HQY"],
    "INTERNET-CONTENT": ["GOOGL", "META", "NFLX", "SPOT", "PINS", "RDDT", "MMYT", "MTCH", "IAC", "YELP", "VZIO", "GRND"],
    "INTRNT-NETWK SLTNS": ["IT", "MSTR", "CSGP", "VRSN", "UPST", "BRZE", "CARG", "NET", "VLTO"],
    "INSURANCE-BROKERS": ["MMC", "AON", "AJG", "WTW", "BRO", "RYAN", "CRVL", "GSHD"],
    "OIL&GAS INTEGRATED": ["XOM", "CVX", "OXY"],
    "OIL&GAS-U S EXPL PRO": ["COP", "EOG", "FANG", "DVN", "EQT", "EXE", "CTRA", "MRO", "PR", "OVV", "APA", "CHRD", "MTDR", "NFG", "CIVI", "CNX", "CRC", "CRGY", "AR", "RRC", "MUR", "MGY", "SM", "NOG", "CRK", "GPOR", "XPRO"],
    "OIL&GAS-ROYALTY TRUST": ["VNOM", "HESM", "BSM"],
    "RETAIL-INTERNET": ["AMZN", "MELI", "CPNG", "LULU", "EBAY", "CHWY", "GLBE", "ETSY", "ACVA"],
    "FIN-INVEST BNK/BKRS": ["GS", "SCHW", "ICE", "CME", "IBKR", "BK", "COIN", "NDAQ", "TW", "STT", "CBOE", "HOOD", "LPLA", "JEF", "HLI", "MKTX", "XP", "EVR", "FRHC", "PJT", "MC", "PIPR", "VIRT", "LAZ", "SNEX"],
    "FNCE-INVSMNT MGT": ["BX", "MS", "KKR", "BN", "APO", "ARES", "OWL", "RJF", "TROW", "TPG", "PFG", "BAM", "NTRS", "CRBG", "CG", "MORN", "ARCC", "BEN", "SF", "HLNE", "SEIC", "IVZ", "STEP", "JHG", "FSK", "AMG", "CNS", "MAIN", "GBDC", "AB", "VCTR", "APAM", "HTGC", "IFS", "FHI", "GCMG", "AMP"],
    "FINANC-PBL INV FDEQT": ["TPL", "BXSL", "STR"],
    "INSURANCE-LIFE": ["PRU", "EQH", "PRI", "VOYA", "JXN", "LNC", "BHF", "PRVA"],
    "BANKS-MONEY CNTR": ["JPM", "BAC", "WFC", "C", "COF"],
    "BANKS-FOREIGN": ["UBS", "BAP"],
    "BANKS-SUPR RGIONAL": ["PNC", "HBAN", "RF", "CFG", "KEY", "CMA", "ZION", "FITB", "TFC", "MTB", "ALLY", "WAL"],
    "BANKS-WST/STHWST": ["BOKF", "ONB", "TCBI", "WAFD", "PRK", "BKU", "IBOC", "BANF", "UCB", "AUB", "FIBK", "CATY", "FHB", "BOH", "CVBF"],
    "BANKS-SOUTHEAST": ["CADE", "FNB", "FBK", "SNV", "HOMB", "OZK", "ABCB"],
    "BANKS-MIDWEST": ["FFIN", "UMBF", "ASB", "FULT", "CBU", "SFNC", "FRME", "NBTB", "CBSH", "COLB", "GBCI", "UBSI", "HWC", "TOWN"],
    "BANKS-NORTHEAST": ["FCNCA", "EWBC", "FHN", "CFR", "PNFP", "SSB", "WTFC", "BPOP", "PB", "WU", "EBC", "FBP", "TBBK"],
    "FINANC-SVINGS & LO": ["WBS", "NYCB", "TFSL", "WSFS", "PFS"],
    "MED-MANAGED CARE": ["UNH", "ELV", "CI", "CNC", "HUM", "MOH", "OSCR", "ALHC"],
    "TRANSPORTATION-SHIP": ["KEX", "FRO", "MATX", "GLNG", "STNG", "TDW", "INSW", "SBLK", "GOGL", "ZIM", "TNK"],
    "MDCAL-WHLSLE DRG": ["MCK", "COR", "CAH", "HSIC"],
    "MEDICAL-PRODUCTS": ["TMO", "ABT", "DHR", "A", "IDXX", "RMD", "MTD", "RVTY", "EXAS", "BRKR", "QGEN", "BIO", "GMEN", "LNTH", "MASI", "GKOS", "BLCO", "MMSI"],
    "MEDICAL-SYSTEMS/EQP": ["ISRG", "SYK", "BSX", "MDT", "BDX", "GEHC", "EW", "DXCM", "STE", "WST", "COO", "ZBH", "WAT", "HOLX", "BAX", "ALGN", "PODD", "NTRA", "TFX", "PEN", "INSP"],
    "METAL PROC & FABRICA": ["RBC", "MLI", "VMI", "ROCK"],
    "CMML SVCS-CNSLTNG": ["TNET", "LOPE", "CNXC", "ABM", "RCM", "LAUR", "QXO", "G"],
    "AUTO MANUFACTURERS": ["TSLA", "GM", "F", "RIVN"],
    "TRNSPRT-EQP MFG": ["OSK", "HOG", "WAB", "TEX", "TRN", "ALG"],
    "LEISRE-MVIES & REL": ["DIS", "LYV", "FWONA", "TKO", "MSGS", "FUN", "CNK", "PRKS", "MANU", "BATRA"],
    "INSRNCE-DIVRSIFIED": ["PGR", "AFL", "MET", "ACGL", "HIG", "CINF", "RGA", "CNA", "UNM", "KNSL", "GL", "RLI", "AXS", "BWIN", "ACT", "FG", "ESGR", "WTM", "CNO"],
    "OFFICE SUPPLIES MFG": ["HNI"],
    "OIL&GAS-TRNSPRT/PIP": ["EPD", "WMB", "ET", "OKE", "KMI", "MPLX", "LNG", "WES", "PAA", "DTM", "KNTK", "AM", "ENLC", "SOBO", "PAGP", "DKL"],
    "OIL&GAS-RFING/MKT": ["PSX", "MPC", "VLO", "DINO", "IEP", "PBF", "CVI", "SUN"],
    "OIL&GAS-FIELD SERVIC": ["HAL", "FIT", "WFRD", "NOV", "WHD", "AROC", "LBRT", "USAC", "KGS", "AESI"],
    "LEISURE-SERVICES": ["CTAS", "ROL", "SCI", "HRB", "PLNT", "LTH", "VVV", "GHC", "UNF", "LRN", "ATGE", "DRVN", "STRA"],
    "CONSUMR PROD-SPECI": ["MSA", "HAS", "AS", "MAT", "THO", "PII", "GOLF", "HAYW", "VSTO", "SIG"],
    "CMP SFTWR-SPC-ENTR": ["TTD"],
    "MEDICAL-ETHICAL DRGS": ["LLY", "JNJ", "ABBV", "MRK", "PFE", "VRTX", "REGN", "BMY", "ZTS", "ALNY", "BIIB", "RPRX", "UTHR", "VTRS", "INCY", "INSM", "SRPT", "NBIX", "CTLT", "ROIV", "ITCI", "RGEN", "VKTX", "EXEL", "JAZZ", "CYTK", "IONS", "BHVN", "RARE", "CORT", "MDGL", "OGN", "ALKS", "CRNX", "TGTX", "PHB", "PRGO", "APLS", "RVMD"],
    "MINING-GLD/SILVR/GMS": ["NEM", "RGLD"],
    "INSRNCE-PRP/CAS/TITL": ["BRK.A", "BRK.B", "CB", "TRV", "ALL", "AIG", "ERIE", "WRB", "MKL", "L", "EG", "RNR", "AFG", "AIZ", "MTG", "SIGI", "THG", "KMPR", "HGTY", "MCY", "NMIH", "PLMR", "SPNT", "FNF", "ORI", "ESNT", "FAF", "RDN", "AGO"],
    "MEDIA-BOOKS": ["WLY"],
    "MEDIA-NEWSPAPERS": ["NWS", "NYT"],
    "PAPER & PAPER PRODUC": ["IP", "SLVM"],
    "TRANSPORTATION-RAIL": ["UNP", "CSX", "NSC", "GATX"],
    "REAL STATE DVLPMT/OPS": ["CBRE", "JLL", "HHH", "HGV", "JOE", "CWK", "NMRK", "EXPI"],
    "FINANCE-REIT": ["HASI", "ESBA"],
    "RETAIL-MJR DSC CHNS": ["WMT", "COST", "TGT", "BJ", "PSMT"],
    "RETAIL/WHLSLE-AUTO": ["CVNA", "KMX", "PAG", "MUSA", "LAD", "AN", "GPI", "ABG", "RUSHA"],
    "RETAIL/WSL-AUTO PRT": ["ORLY", "AZO"],
    "RETAIL-SPECIALTY": ["TSCO", "ULTA", "DKS", "MUSA", "LAD", "ASO"],
    "RETAIL-RESTAURANTS": ["MCD", "SBUX", "CMG", "YUM", "QSR", "DRI", "YUMC", "CAVA", "DPZ", "WING", "TXRH", "ARMK", "SHAK", "SG", "EAT", "WEN", "CAKE"],
    "TELECOM SVCS-FOREIGN": ["FYBR", "CCOI", "LBTYA"],
    "TELCOM-INFRASTR": ["SATS", "ASTS", "IRDM"],
    "STEEL-PRODUCERS": ["NUE", "STLD", "RS", "X", "CMC", "CLF"],
    "TELCOM-CONS PROD": ["MSI", "GRMN", "UI"],
    "TEXTILES": ["AIN"],
    "TOBACCO": ["PM", "MO"],
    "BLDG-HAND TOOLS": ["SWK", "SNA"],
    "TRNSPORTATION-TRCK": ["ODFL", "JBHT", "XPO", "SAIA", "KNX", "LSTR", "SNDR", "ARCB", "WERN"],
    "MACHINERY-FARM": ["DE", "CNH", "TTC", "AGCO", "SITE", "FSS", "ACA"],
    "MCHNRY-CNSTR/MNG": ["CAT", "PCAR"],
    "UTILITY-WATER SUPPLY": ["AWK", "WTRG", "AWR", "CWT"],
    "WHOLESALE-ELECT": ["GWW", "FAST", "FERG", "GPC", "POOL", "AIT", "WCC", "MSM", "UGI"],
    "TELCOM SVC-WIRLES": ["TMUS", "VZ", "T", "LBRDA", "USM", "TIGO", "TDS"],
    "ELEC-SEMICON FBLSS": ["ARM", "NVDA", "AVGO", "AMD", "QCOM", "ADI", "MRVL", "NXPI", "MPWR", "MCHP", "ON", "SWKS", "QRVO", "ALAB", "MTSI", "LSCC", "CRUS", "PI", "RMBS", "SITM", "ALGM", "SLAB", "POWI", "IPGP", "SMTC", "DIOD", "SYNA", "AMBA"],
    "ELEC-SEMICON MFG": ["TSM", "TXN", "INTC", "GFS", "AMKR", "TSEM", "FORM"]
}

# 3. Sidebar Inputs
with st.sidebar:
    st.header("Settings", anchor=False)
    benchmark = st.selectbox("Benchmark", ["^GSPC", "^IXIC"], index=0, label_visibility="collapsed")
    lookback = st.slider("Lookback Period (Days)", 20, 250, 90, label_visibility="collapsed")
    top_n = st.number_input("Top N for Group Avg", value=5, label_visibility="collapsed")
    
    # Add Bongo Cat at the bottom of sidebar
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; padding: 20px 0;">
        <div style="font-size: 80px;">🐱</div>
        <p style="font-size: 12px; color: gray;">Bongo Cat</p>
    </div>
    """, unsafe_allow_html=True)

# 4. Data Processing Function
def get_rs_data(tickers, benchmark_ticker, period):
    try:
        # Fetch data for all tickers + benchmark
        all_tickers = tickers + [benchmark_ticker]
        data = yf.download(all_tickers, period="1y", interval="1d", progress=False)['Close']
        
        # Calculate RS: (Stock / Benchmark)
        rs_series = data[tickers].div(data[benchmark_ticker], axis=0)
        
        # Get the performance over the lookback period
        rs_perf = ((rs_series.iloc[-1] / rs_series.iloc[-period]) - 1) * 100
        
        # Normalize RS to 1-99
        ranks = rs_perf.rank(pct=True) * 99
        
        return rs_perf, ranks
    except Exception as e:
        return None, None

# 5. Main Display
st.markdown("""
<style>
    /* Smaller font sizes */
    .industry-header {
        font-size: 14px !important;
        font-weight: bold;
        color: white;
        background-color: #1f77b4;
        padding: 8px 12px;
        border-radius: 4px;
        margin-bottom: 8px;
        margin-top: 12px;
    }
    .metric-row {
        font-size: 12px;
    }
    /* Dark table styling */
    .dataframe {
        background-color: #2b2b2b !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("<h3 style='font-size: 16px; margin-bottom: 15px;'>📊 Relative Strength Screener</h3>", unsafe_allow_html=True)

# Create horizontal layout for all industries
for industry_name, tickers in INDUSTRIES.items():
    # Collapsible section with dropdown
    with st.expander(f"**{industry_name}** ({len(tickers)} tickers)", expanded=False):
        # Display members list in sidebar format
        st.markdown(f"<p style='font-size: 11px; color: #888;'>Members: {', '.join(tickers)}</p>", unsafe_allow_html=True)
        
        with st.spinner(f"Loading {industry_name}..."):
            try:
                perf, rs_scores = get_rs_data(tickers, benchmark, lookback)
                
                if rs_scores is None:
                    st.error(f"Error loading {industry_name}")
                    continue
                
                # Calculate Group Average of Top N
                top_n_scores = rs_scores.nlargest(int(top_n))
                group_avg = top_n_scores.mean()
                
                # Display Group Average Metric in smaller size
                col1, col2, col3 = st.columns([2, 2, 6])
                col1.markdown(f"<p style='font-size: 12px;'><b>Group Avg RS:</b> {group_avg:.2f}</p>", unsafe_allow_html=True)
                col2.markdown(f"<p style='font-size: 12px;'><b>Total:</b> {len(tickers)}</p>", unsafe_allow_html=True)
                
                # Build Results Table
                df_results = pd.DataFrame({
                    "Ticker": tickers,
                    "RS Score": rs_scores.values,
                    "Perf (%)": perf.values
                }).sort_values(by="RS Score", ascending=False)
                
                # Style dataframe with dark theme
                styled_df = df_results.style\
                    .background_gradient(subset=["RS Score"], cmap="RdYlGn", vmin=0, vmax=100)\
                    .set_properties(**{'background-color': '#3a3a3a', 'color': 'white', 'border-color': '#555'})\
                    .format({"RS Score": "{:.2f}", "Perf (%)": "{:.2f}"})\
                    .set_uuid(f"table_{industry_name.replace(' ', '_')}")
                
                st.dataframe(styled_df, use_container_width=True, height=400)
                
            except Exception as e:
                st.error(f"Error loading {industry_name}: {str(e)}")
