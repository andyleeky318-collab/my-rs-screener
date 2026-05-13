import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# 1. Setup Streamlit Page
st.set_page_config(page_title="Chrome Sector RS", layout="wide")
st.title("🚀 Chrome Sector Relative Strength")

# 2. Cleaned Industry Database (Preserved as requested)
INDUSTRIES = {
    "Nuclear": ["URA", "NLR", "CEG", "CCJ", "OKLO", "UUUU", "SMR"],
    "MAG7": ["AAPL", "GOOGL", "NVDA", "META", "MSFT", "AMZN", "TSLA"],
    "ETF": ["XLK", "XLF", "XLE", "XLP", "XLU", "XLI", "XLY", "XLV", "XLC", "XLB"],
    "SPACE": ["UFO", "VSAT", "ARKX", "PL", "RKLB", "ASTS"],
    "CATHIE WOOD": ["ARKG", "ARKK", "ARKQ", "ARKW", "ARKF", "ARKX"],
    "CHINA": ["FUTU", "LI", "KWEB", "XPEV", "NIO", "PDD", "BIDU", "JD", "BABA"],
    "DATA CENTER / AI HOSTING": ["WGMI", "CRWV", "NBIS", "IREN", "WULF", "CORZ", "CIFR", "HUT", "BTDR"],
    "ENERGY SOLAR": ["TAN", "SEDG", "ENPH", "FSLR", "ARRY", "SHLS", "CSIQ", "RUN"],
    "COML SVCS-ADVRTSNG": ["OMC", "DJT"],
    "AEROSPACE/DEFENSE": ["ITA", "RTX", "LMT", "HON", "BA", "GD", "NOC", "TDG", "LHX", "HWM", "AXON", "HEI", "LDOS", "TDY", "TXT", "FTAI", "CW", "BWXT", "HII", "CR", "DRS", "LOAR", "AVAV", "HXL", "KTOS", "MIR", "OSIS", "AIR", "MRCY"],
    "AGRICULTURAL OPRTIONS": ["ADM", "BG", "PPC", "CALM", "SEB"],
    "TRNSPRT-AIR FREIGHT": ["UPS", "FDX"],
    "TRANSPORTATION-SVCS": ["DASH", "EXPD", "CHRW", "CART", "GXO", "HUBG", "UBER", "PFGC", "SARO", "VNT", "VRRM", "CAAP"],
    "TRNSPRTTIN-AIRLNE": ["JETS", "DAL", "UAL", "LUV", "AAL", "ALK", "CPA", "SKYW"],
    "ENERGY-ALT/OTHER": ["BIP", "TLN", "CWEN", "BEPC"],
    "MINING-METAL ORES": ["AA", "SCCO", "FCX", "CCJ", "CRS", "ATI", "MP", "TECK"],
    "APPAREL-SHOES & REL": ["NKE", "DECK", "ONON", "RL", "BIRK", "CROX", "LEVI", "VFC", "GIL", "PVH", "COLM", "KTB", "SHOO"],
    "RETAIL-APPRL/SHOES/ACC": ["TJX", "ROST", "BURL", "TPR", "GAP", "ANF", "BBWI", "CPRI", "BOOT", "AEO", "URBN", "CRI", "BKE"],
    "AUTO/TRCK-ORGNL EQP": ["ITW", "CMI", "APTV", "ITT", "DCI", "ALSN", "ALV", "GNTX", "LEA", "BC", "ATMU", "VC", "BWA"],
    "AUTO/TRCK-RPLC PRTS": ["LKQ", "DORM", "AAP"],
    "BEVERAGES-ALCOHOLIC": ["STZ", "TAP", "SAM"],
    "BEV-NON-ALCOHOLIC": ["KO", "MNST", "CCEP", "COKE", "BRBR", "CELH", "FIZZ"],
    "MEDICAL-BIOMED/BTH": ["AMGN", "GILD", "MRNA", "ILMN", "SMMT", "PCVX", "BMRN", "TECH", "NUVL", "ELAN", "HALO", "RNA", "KRYS", "ADMA", "BBIO", "IMVT", "ACLX", "AXSM", "CRSP", "DNLI", "ALVO", "APGE", "DYN", "RYTM", "KYMR", "EWTX", "PTGX", "TWST", "TXG", "CGON", "JANX", "ARWR", "VERA", "NVAX", "CLDX"],
    "MEDIA-RADIO/TV": ["FOX", "SIRI", "NXST", "TGNA"],
    "TELCOM-SVC-CBL/SAT": ["CMCSA", "CHTR"],
    "LEISRE-GAMNG/EQUIP": ["FLUT", "LVS", "MGM", "WYNN", "CZR", "LNW", "BYD", "RSI", "DKNG", "CHDN", "PENN"],
    "CHEMICALS-AG": ["NTR", "CTVA", "CF", "MOS", "FMC", "SMG"],
    "CHEMICALS-BASIC": ["DD", "ESI", "AVNT", "HUN", "IOSP", "DOW", "LYB", "WLK", "AVTR", "CE", "EMN", "CC"],
    "CHEMICALS-SPECIALTY": ["LIN", "ECL", "APD", "ALB", "CHX", "CBT", "NEU", "KWR", "HWKN", "MTX", "TROX", "OLN", "FUL", "WDFC", "AZZ", "UFPT"],
    "ENERGY COAL": ["HCC", "BTU", "ARLP", "AMR"],
    "MEDIA-DIVERSIFIED": ["WMG"],
    "COMPTER-NETWRKING": ["ANET", "CSCO", "CALX"],
    "COMPTR-DATA STRGE": ["DRAM", "WDC", "STX", "MU", "SNDK"],
    "CMP-HRDWRE/PERIP": ["DELL", "HPQ", "SMCI", "HPE", "ZBRA", "NATL"],
    "CONTAINERS/PACKAGING": ["SW", "BALL", "PKG", "AVY", "AMCR", "OC", "CCK", "ATR", "GPK", "SLGN", "SON", "SEE", "GEF", "OI"],
    "OIL&GAS-DRILLING": ["SLB", "BKR", "NE", "VAL", "HP", "SDRL"],
    "BLDG-CMENT/CNCRT": ["CRH", "MLM", "VMC", "EXP", "KNF", "USLM"],
    "CMPTER-TECH SRVCS": ["PAYX", "MSCI", "VRSK", "ZS", "TYL", "GDDY", "J", "FDS", "AKAM", "DBX", "EXLS", "KD", "MARA", "EEFT", "DXC", "CORZ", "AVPT", "ACN", "CTSH", "CDW", "CACI", "PSN", "EPAM", "DOX", "KBR", "GLOB", "NSIT", "SAIC", "ASGN"],
    "RETAIL-DPRTMNT STRS": ["DDS", "M", "KSS"],
    "RETAIL-DISCNT&VARI": ["DG", "DLTR", "FIVE", "OLLI"],
    "RETAIL-DRUG STORES": ["CVS"],
    "UTILITY-ELCTRIC PWR": ["NEE", "SO", "CEG", "DUK", "AEP", "SRE", "D", "VST", "PEG", "PCG", "EXC", "XEL", "ED", "EIX", "WEC", "ETR", "DTE", "FE", "PPL", "AEE", "ES", "CMS", "NRG", "CNP", "LNT", "EVRG", "AES", "PNW", "OGE", "IDA", "POR", "ORA", "BKH", "TXNM", "NWE", "MGEE"],
    "ELECTRICAL POWER/EQPMT": ["ETN", "GEV", "AME", "ROK", "HUBB", "RRX", "GNRC", "AYI", "BDC", "ENS", "FLNC", "SMR", "ATKR", "PBW", "POWL", "BE", "ENVX"],
    "TELCOM-FIBR OPTCS": ["AAOI", "COHR", "CIEN", "FN", "LITE"],
    "ELEC-PARTS": ["APH", "GLW", "NVT", "CAMT", "TEL"],
    "ELEC-SCNTIFIC/MSRNG": ["PH", "EMR", "KEYS", "FTV", "CGNX", "NOVT", "ST", "NXT", "ITRI", "ESE", "SXI", "MTRN"],
    "ELEC-SEMICNDCTR EQP": ["ASML", "KLAC", "AMAT", "LRCX", "ONTO", "NVMI", "TER", "AEIS", "MKSI", "ENTG", "ACLS"],
    "ELEC-CONTRACT MFG": ["SOLS", "VRT", "FLEX", "PLXS", "JBL"],
    "ELEC-MISC PRODUCTS": ["OLED", "LFUS", "VSH"],
    "WHOLESALE-ELECT": ["SNX", "ARW", "AVT", "REZI", "GWW", "FAST", "FERG", "GPC", "POOL", "AIT", "WCC", "MSM", "UGI"],
    "RETAIL-CNSMR ELEC": ["BBY", "GME"],
    "CONSUMER PROD-ELEC": ["SN", "ROKU", "WHR", "SPB", "AAPL"],
    "BLDG-HEAVY CONSTR": ["PWR", "EME", "FIX", "ACM", "TTEK", "MTZ", "APG", "FLR", "DY", "STRL", "ROAD", "GVA", "PRIM"],
    "BLDG-RSIDNT/COMML": ["BLD", "IBP", "EXPO", "IESC", "DHI", "LEN", "NVR", "PHM", "TOL", "MTH", "TMHC", "KBH", "SKY", "MHO", "TPH", "FTDR", "GRBK", "DFH", "CCS", "LGIH"],
    "BLDG-MBILE/MFG & RV": ["CVCO", "PATK"],
    "POLLUTION CONTROL": ["WM", "RSG", "CLH", "CWST"],
    "COMML SVCS-LEASING": ["URI", "AER", "UHAL", "WSC", "R", "AL", "HRI", "WD", "CAR", "MGRC", "PRG"],
    "FINANCE-CARD/PMTPR": ["AXP", "SYF", "AFRM", "FCFS", "SLM", "V", "MA", "PYPL", "GPN", "CPAY", "FOUR", "WEX", "PAY", "RELY"],
    "FINANCE-CONS LOAN": ["RKT", "OMF", "ENVA", "NNI"],
    "FINANCE-CMRCL LOAN": ["OBDC", "PFSI", "CACC"],
    "FINANCE-BLANK CHECK": ["BCSF", "LOCL", "MNTN", "MSDL", "NCDL", "OKLO", "PSBD", "RMI", "SBXD"],
    "FINANCIAL SVC-SPEC": ["BLK", "SPGI", "MCO", "EFX", "TRU", "ICLR", "BAH", "MEDP", "CRL", "FCN", "MMS", "CBZ", "NSP", "ICFI", "EVH", "FA"],
    "WHOLESALE-FOOD": ["SYY", "USFD"],
    "RETAIL-SPR/MINI MKTS": ["KR", "SFM", "ACI", "TBBB", "CASY"],
    "FOOD-PACKAGED": ["KHC", "GIS", "CAG", "SMPL", "MDLZ", "KDP", "HSY", "CPB", "SJM", "POST", "LANC", "FLO", "NOMD", "UTZ"],
    "FOOD-MEAT PRODUCTS": ["TSN", "HRL"],
    "FOOD-MISC PREP": ["PEP", "IFF", "MKC", "LW", "INGR", "DAR", "BCPC", "ASH", "JJSF", "SXT", "TR"],
    "FOOD-CONFECTIONERY": ["FRPT", "BROS"],
    "BLDG-WOOD PRDS": ["UFPI", "LPX", "TREX"],
    "UTILITY-GAS DSTRIBTN": ["TRGP", "CQP", "ATO", "NI", "MDU", "BIPC", "SWX", "NJR", "OGS", "SR", "CPK", "EE"],
    "RTAIL-HME FRNSHNGS": ["MBC", "WSM", "W", "RH"],
    "RETL WHSLE BLDG PRDS": ["HD", "LOW", "BLDR", "FND", "CNM", "BCC"],
    "MEDCAL-HOSPITALS": ["HCA", "THC", "UHS"],
    "MED-LONG-TRM CARE": ["CHE", "PACS", "SEM", "SGRY", "ARDT", "ENSG", "ADUS"],
    "MEDICAL-SERVICES": ["DVA", "SOLV", "EHC", "ACHC", "RDNT", "OPCH", "HIMS", "GH", "BTSG", "CON", "AZTA"],
    "LEISURE-LODGING": ["MAR", "HLT", "RCL", "CCL", "VIK", "H", "NCLH", "MTN", "WH", "CHH", "RRR", "TNL", "VAC"],
    "COSMETICS/PERSNL CRE": ["PG", "CL", "KMB", "KVUE", "EL", "CHD", "CLX", "ELF", "IPAR"],
    "SOAP & CLNG PREPARAT": ["REYN", "ENR"],
    "DVRSIFIED OPRTIONS": ["MMM", "RLX", "WMS", "AWI", "BRC", "YETI", "LCII"],
    "MCHNRY-GEN INDSTRL": ["GE", "TT", "CARR", "JCI", "IR", "XYL", "DOV", "LII", "PNR", "IEX", "GGG", "NDSN", "LECO", "WWD", "AAON", "FLS", "MIDD", "MOD", "WTS", "BMI", "ZWS", "ESAB", "TKR", "GTLS", "GTES", "FELE", "KAI", "MWA", "NPO", "CXT", "OII", "SYM"],
    "CHEMICALS-PAINTS": ["SHW", "PPG", "RPM", "AXTA"],
    "COMPTER SFTWR-SCRITY": ["BUG", "FTNT", "PANW", "CRWD", "CHKP", "RBRK", "RPD"],
    "COMPTER SFTWR-ENTR": ["IGV", "TWLO", "MSFT", "ORCL", "CRM", "IBM", "NOW", "ADP", "DOCN", "PLTR", "ADSK", "ROP", "TEAM", "SNOW", "VEEV", "HUBS", "PTC", "MDB", "MANH", "TOST", "MNDY", "WDAY", "SSNC", "GWRE", "BSY", "PEGA", "QTWO", "APPF", "BOX", "WK"],
    "COMPTER SFTWR-DSGN": ["ADBE", "INTU", "SNPS", "CDNS", "IOT", "DT", "TRMB", "WIX"],
    "CMPTR SFTWR-FINCL": ["FICO", "FIS", "NU", "SHOP"],
    "CMP SFTWR-GAMING": ["EA", "TTWO", "RBLX"],
    "CMP SFTWR-DBASE": ["DDOG"],
    "COMPTER SFTWR-DSKTP": ["ZM", "SNAP", "Z"],
    "CMPTR SFTWR-MDCL": ["APP", "HQY"],
    "INTERNET-CONTENT": ["GOOGL", "META", "NFLX", "SPOT", "PINS", "RDDT", "MMYT", "MTCH", "IAC", "YELP", "GRND"],
    "INTRNT-NETWK SLTNS": ["IT", "MSTR", "CSGP", "VRSN", "UPST", "BRZE", "CARG", "NET", "VLTO"],
    "INSURANCE-BROKERS": ["AON", "AJG", "WTW", "BRO", "RYAN", "CRVL", "GSHD"],
    "OIL&GAS INTEGRATED": ["XOM", "CVX", "OXY"],
    "OIL&GAS-U S EXPL PRO": ["COP", "EOG", "FANG", "DVN", "EQT", "EXE", "CTRA", "PR", "OVV", "APA", "CHRD", "MTDR", "NFG", "CNX", "CRC", "CRGY", "AR", "RRC", "MUR", "MGY", "SM", "NOG", "CRK", "GPOR", "XPRO"],
    "OIL&GAS-ROYALTY TRUST": ["VNOM", "HESM", "BSM"],
    "RETAIL-INTERNET": ["AMZN", "MELI", "CPNG", "LULU", "EBAY", "CHWY", "GLBE", "ETSY", "ACVA"],
    "FIN-INVEST BNK/BKRS": ["GS", "SCHW", "ICE", "CME", "IBKR", "BK", "COIN", "NDAQ", "TW", "STT", "CBOE", "HOOD", "LPLA", "JEF", "HLI", "MKTX", "XP", "EVR", "FRHC", "PJT", "MC", "PIPR", "VIRT", "LAZ", "SNEX"],
    "FNCE-INVSMNT MGT": ["BX", "MS", "KKR", "BN", "APO", "ARES", "OWL", "RJF", "TROW", "TPG", "PFG", "BAM", "NTRS", "CRBG", "CG", "MORN", "ARCC", "BEN", "SF", "HLNE", "SEIC", "IVZ", "STEP", "JHG", "FSK", "AMG", "CNS", "MAIN", "GBDC", "AB", "VCTR", "APAM", "HTGC", "IFS", "FHI", "GCMG", "AMP"],
    "FINANC-PBL INV FDEQT": ["TPL", "BXSL"],
    "INSURANCE-LIFE": ["PRU", "EQH", "PRI", "VOYA", "JXN", "LNC", "BHF", "PRVA"],
    "BANKS-MONEY CNTR": ["JPM", "BAC", "WFC", "C", "COF"],
    "BANKS-FOREIGN": ["UBS", "BAP"],
    "BANKS-SUPR RGIONAL": ["PNC", "HBAN", "RF", "CFG", "KEY", "ZION", "FITB", "TFC", "MTB", "ALLY", "WAL"],
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
    "INSRNCE-PRP/CAS/TITL": ["BRK.B", "CB", "TRV", "ALL", "AIG", "ERIE", "WRB", "MKL", "L", "EG", "RNR", "AFG", "AIZ", "MTG", "SIGI", "THG", "KMPR", "HGTY", "MCY", "NMIH", "PLMR", "SPNT", "FNF", "ORI", "ESNT", "FAF", "RDN", "AGO"],
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
    "TELCOM SVC-WIRLES": ["TMUS", "VZ", "T", "LBRDA", "USM", "TIGO", "TDS"],
    "ELEC-SEMICON FBLSS": ["ARM", "NVDA", "AVGO", "AMD", "QCOM", "ADI", "MRVL", "NXPI", "MPWR", "MCHP", "ON", "SWKS", "QRVO", "ALAB", "MTSI", "LSCC", "CRUS", "PI", "RMBS", "SITM", "ALGM", "SLAB", "POWI", "IPGP", "SMTC", "DIOD", "SYNA", "AMBA"],
    "ELEC-SEMICON MFG": ["TSM", "TXN", "INTC", "GFS", "AMKR", "TSEM", "FORM"]
}

# 3. Sidebar Inputs
with st.sidebar:
    st.header("Settings")
    benchmark = st.selectbox("Benchmark", ["^GSPC", "^IXIC"], index=0)
    top_n = st.number_input("Top N for Group Avg", value=5, min_value=1)
    
    if st.button("Clear Cache & Refresh"):
        st.cache_data.clear()

# 4. UPDATED DATA FETCHING (Includes EMA logic)
@st.cache_data(ttl=3600)
def get_rs_data_cached(tickers_tuple, benchmark_ticker):
    tickers = list(tickers_tuple)
    try:
        all_tickers = tickers + [benchmark_ticker]
        # Download High, Low, and Close for EMA Cloud calculation
        data = yf.download(all_tickers, period="2y", interval="1d", progress=False)
        
        close_data = data['Close']
        high_data = data['High']
        low_data = data['Low']

        valid_tickers = [t for t in tickers if t in close_data.columns and close_data[t].notna().sum() >= 252]
        if not valid_tickers: return None, None, []

        # RS Calculation Logic
        offsets = [63, 126, 189, 252]
        weights = [0.4, 0.2, 0.2, 0.2]

        def calculate_weighted_score(series):
            score = 0
            for offset, weight in zip(offsets, weights):
                perf = series.iloc[-1] / series.iloc[-offset]
                score += (perf * weight)
            return score

        bench_weighted = calculate_weighted_score(close_data[benchmark_ticker])

        stock_scores = {}
        inside_cloud_tickers = []

        for ticker in valid_tickers:
            # RS Score
            stock_weighted = calculate_weighted_score(close_data[ticker])
            total_score = (stock_weighted / bench_weighted) * 100
            stock_scores[ticker] = total_score

            # 21 EMA Cloud Logic
            # EMA of Highs and Lows
            ema_high = high_data[ticker].ewm(span=21, adjust=False).mean().iloc[-1]
            ema_low = low_data[ticker].ewm(span=21, adjust=False).mean().iloc[-1]
            current_close = close_data[ticker].iloc[-1]

            if ema_low <= current_close <= ema_high:
                inside_cloud_tickers.append(ticker)

        rs_perf = pd.Series(stock_scores)
        ranks = rs_perf.rank(pct=True) * 99
        
        return rs_perf, ranks, inside_cloud_tickers
    except Exception as e:
        st.error(f"Error: {e}")
        return None, None, []

# 5. UI Layout & Logic
all_data = []
progress_bar = st.progress(0)
status_text = st.empty()

industry_items = list(INDUSTRIES.items())
for idx, (industry_name, tickers) in enumerate(industry_items):
    status_text.text(f"Processing {industry_name}...")
    perf, rs_scores, cloud_tickers = get_rs_data_cached(tuple(tickers), benchmark)
    
    if rs_scores is not None:
        top_n_scores = rs_scores.nlargest(int(top_n))
        group_avg = top_n_scores.mean()
        df_tickers = pd.DataFrame({"Ticker": rs_scores.index, "RS Score": rs_scores.values}).sort_values(by="RS Score", ascending=False)
        all_data.append({
            "Industry": industry_name, 
            "Group RS": group_avg, 
            "Tickers": df_tickers,
            "Cloud Tickers": cloud_tickers
        })
    
    progress_bar.progress((idx + 1) / len(industry_items))

status_text.empty()
progress_bar.empty()

# 6. Compact Display Logic
if all_data:
    df_main = pd.DataFrame([{"Industry": item["Industry"], "Group RS": item["Group RS"]} for item in all_data])

    sort_by = st.selectbox("Sort by", ["Group RS (High to Low)", "Industry (A-Z)"])
    df_main = df_main.sort_values("Group RS" if "RS" in sort_by else "Industry", ascending=("A-Z" in sort_by))

    st.markdown("""
    <style>
    .ticker-badge { display: inline-block; margin: 1px 3px; padding: 1px 5px; border: 1px solid #444; border-radius: 3px; font-size: 11px; background-color: #1e1e1e; color: #eee; }
    .cloud-badge { background-color: #2e4a3e; border: 1px solid #4ecdc4; color: #4ecdc4; font-weight: bold; }
    .ticker-name { font-weight: bold; color: #ffffff; margin-right: 4px; }
    .ticker-rs { color: #4ecdc4; }
    table { width:100%; border-collapse: collapse; }
    th { padding: 4px 8px; background-color: #1f77b4; color: white; font-size: 12px; }
    td { padding: 4px 8px; border-bottom: 1px solid #333; font-size: 12px; }
    </style>
    """, unsafe_allow_html=True)

    table_html = """<table>
    <thead><tr>
    <th style="text-align: left;">Industry</th>
    <th style="text-align: center; width: 80px;">Group RS</th>
    <th style="text-align: left;">Tickers (Ranked)</th>
    <th style="text-align: left; width: 150px;">21 EMA Cloud</th>
    </tr></thead><tbody>"""

    for i, row in df_main.iterrows():
        item = next(d for d in all_data if d["Industry"] == row["Industry"])
        
        # Rank Tickers HTML
        ticker_html = "".join([f'<div class="ticker-badge"><span class="ticker-name">{r["Ticker"]}</span><span class="ticker-rs">{r["RS Score"]:.1f}</span></div>' for _, r in item["Tickers"].iterrows()])
        
        # Cloud Tickers HTML
        cloud_html = "".join([f'<div class="ticker-badge cloud-badge">{t}</div>' for t in item["Cloud Tickers"]])
        if not cloud_html: cloud_html = '<span style="color:#666; font-size: 10px;">None</span>'

        bg_color = "#262730" if i % 2 == 0 else "#0e1117"
        
        # REORDERED CELLS: Tickers first, Cloud last
        table_html += f"""<tr style="background-color: {bg_color};">
        <td style="font-weight: bold;">{row['Industry']}</td>
        <td style="text-align: center; color: #4ecdc4; font-weight: bold;">{row['Group RS']:.1f}</td>
        <td>{ticker_html}</td>
        <td>{cloud_html}</td>
        </tr>"""

    table_html += "</tbody></table>"
    st.markdown(table_html, unsafe_allow_html=True)