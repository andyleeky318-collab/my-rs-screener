import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# 1. Setup Streamlit Page
st.set_page_config(page_title="Chrome Sector RS", layout="wide")
st.title("🚀 Chrome Sector Relative Strength & Patterns")

# 2. Cleaned Industry Database (Preserved as requested)
INDUSTRIES = {
    "Crypto": ["MSTR", "CRCL", "COIN", "IBIT"],
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
    "CMPTER SFTWR-FINCL": ["FICO", "FIS", "NU", "SHOP"],
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

# Cleaned Known Stocks List Reference Array
KNOWN_STOCKS = [
    'AA', 'ABBV', 'ALAB', 'AMGN', 'APO', 'BOTZ', 'CRCL', 'CRWV', 'D', 'DRAM', 'DUK', 'EEM', 'EWJ', 'EXC', 'FIGR', 
    'GEV', 'GILD', 'GXC', 'HON', 'JEF', 'JKS', 'KMI', 'KRMN', 'LIN', 'MNST', 'NASA', 'NEM', 'NTR', 'NTAP', 'OR', 
    'OWL', 'Q', 'QQQ', 'RNG', 'RKT', 'SCCO', 'SHLD', 'SO', 'SOLS', 'SPMO', 'SPY', 'SPHB', 'TSEM', 'UNP', 'VTV', 
    'VUG', 'WGMI', 'WMB', 'XEL', 'XMAG', 'XYZ', 'ZIM','VICR', 'SLX', 'CBOE', 'SIMO', 'FLEX', 'POWL', 'VLO', 'DOCN', 
    'IYZ', 'LNG', 'AAOI', 'AXTI', 'TSEM', 'USO', 'JNJ', 
    'HP', 'GLD', 'ALB', 'BUG', 'BX', 'DOW', 'VZ', 'REMX', 'GDX', 'SIL', 'VEEV', 'SNDK', 'TLT', 'APH', 'ARM', 'FANG', 
    'NBIS', 'NVT', 'OXY', 'FORM', 'IBIT', 'QTUM', 'IAI', 'KWEB', 'IHI', 'UFO', 'ITA', 'IYT', 'CVS', 'HUM', 'NEE', 
    'HPE', 'PLAB', 'INOD', 'TTMI', 'CCJ', 'BE', 'SLV', 'PICK', 'COPX', 'MAR', 'XAR', 'VSCO', 'GLW', 'ANF', 'AEO', 
    'AEP', 'GH', 'SANM', 'ROK', 'PSN', 'IAT', 'HROW', 'PL', 'AVAV', 'CIEN', 'COHR', 'NU', 'WULF', 'IREN', 'CIFR', 
    'RDW', 'PH', 'LITE', 'ACHR', 'CACI', 'CRS', 'URA', 'NVO', 'NLR', 'ITB', 'MVST', 'EOSE', 'APP', 'RKLB', 'ASTS', 
    'IONQ', 'RMBS', 'RTX', 'NOC', 'LMT', 'HON', 'ONDS', 'CLS', 'LEU', 'VRT', 'VST', 'NRG', 'CEG', 'SMCI', 'CRDO', 
    'SOFI', 'XLP', 'XLE', 'HIMS', 'HOOD', 'GEV', 'XLV', 'HACK', 'XOP', 'CIBR', 'ICLN', 'XLB', 'XLU', 'XLRE', 'IGV', 
    'XLF', 'IPAY', 'XLC', 'XLI', 'KRE', 'XLK', 'CLOU', 'KBE', 'XME', 'XTL', 'JETS', 'SMH', 'XLY', 'XHB', 
    'BLOK', 'XBI', 'XRT', 'MJ', 'META', 'MSFT', 'AAPL', 'AMZN', 'GOOGL', 'NVDA', 'TSLA', 'ARKX', 'ARKQ', 'ARKF', 
    'ARKW', 'ARKK', 'ARKG', 'CCL', 'RCL', 'UAL', 'BA', 'DAL', 'NCLH', 'AAL', 'LUV', 'SAVE', 'PINS', 'SNAP', 'TWTR', 
    'IBKR', 'SCHW', 'JPM', 'MS', 'GS', 'BAC', 'WFC', 'SPGI', 'BLK', 'NDAQ', 'C', 'LI', 'BIDU', 'NIO', 'XPEV', 'TCEHY', 
    'BABA', 'PDD', 'JD', 'DQ', 'JKS', 'ENPH', 'FSLR', 'TAN', 'SEDG', 'CSIQ', 'SPWR', 'RUN', 'PBW', 'CLX', 'PG', 
    'EL', 'RMS', 'LVMH', 'LULU', 'SBUX', 'NKE', 'KER', 'MELI', 'EBAY', 'FDX', 'UPS', 'SE', 'JMIA', 'ETSY', 'SHOP', 
    'Z', 'OPEN', 'CHWY', 'BIGC', 'CVNA', 'BARK', 'GM', 'BLNK', 'QS', 'F', 'RIVN', 'FCEL', 'CHPT', 'LCID', 'LAZR', 
    'VLDR', 'UPST', 'PYPL', 'AFRM', 'V', 'MA', 'AXP', 'SQ', 'BITO', 'COIN', 'RIOT', 'MARA', 'MSTR', 'SI', 
    'DKNG', 'PENN', 'BETZ', 'REGN', 'VRTX', 'MRK', 'UNH', 'TMO', 'ISRG', 'ABT', 'NARI', 'IDXX', 'TDOC', 'CRSP', 
    'BRK.B', 'ETN', 'CAT', 'BLD', 'U', 'RBLX', 'SKLZ', 'FSLY', 'TRIP', 'EXPE', 'BKNG', 'ABNB', 'DIS', 'WMT', 
    'COST', 'TGT', 'LOW', 'HD', 'DT', 'SNPS', 'CDNS', 'MDB', 'ORCL', 'NOW', 'ADP', 'SNOW', 'ANSS', 'DDOG', 
    'FROG', 'ADSK', 'INTU', 'TEAM', 'WDAY', 'CRM', 'PAYC', 'ANET', 'ADBE', 'ACN', 'EPAM', 'ZM', 'TTD', 'TWLO', 
    'DASH', 'APPS', 'DOCU', 'AI', 'COUP', 'AKAM', 'CYBR', 'QLYS', 'PANW', 'FTNT', 'CRWD', 'TENB', 'OKTA', 'ZS', 
    'NET', 'S', 'UMC', 'ASML', 'KEYS', 'CRUS', 'AMD', 'AVGO', 'MU', 'KLAC', 'TXN', 'QRVO', 'TSM', 'SWKS', 'AMBA', 
    'STM', 'MCHP', 'ON', 'QCOM', 'SOXX', 'MRVL', 'ADI', 'LRCX', 'AMAT', 'WDC', 'NXPI', 'TER', 'MPWR', 'INTC', 
    'GFS', 'STX', 'A', 'ZBRA', 'ENTG', 'ONTO', 'TRMB', 'BNTX', 'PFE', 'MRNA', 'NVAX', 'FCX', 'CF', 'DRI', 
    'PEP', 'XOM', 'LLY', 'CL', 'MCD', 'KO', 'ATVI', 'GE', 'CVX', 'FISV', 'DE', 'WM', 'HLT', 'FUTU', 'UBER', 
    'TIGR', 'EQIX', 'DPZ', 'CSCO', 'COKE', 'SONY', 'FDS', 'MCO', 'GRAB', 'PTON', 'AMT', 'LIT', 'CMG', 'IPO', 
    'PSTG', 'INMD', 'NNDM', 'MP', 'FUBO', 'SPOT', 'ALGN', 'PZZA', 'LOVE', 'LMND', 'POOL', 'DADA', 'PLTR', 'ROKU', 
    'CELH', 'BTWN', 'AZPN', 'NFLX', 'DHI', 'DELL', 'GOOG'
]
# Ensure uniqueness
KNOWN_STOCKS = list(set(KNOWN_STOCKS))

# 3. Sidebar Inputs
with st.sidebar:
    st.header("Settings")
    benchmark = st.selectbox("Benchmark", ["^GSPC", "^IXIC"], index=0)
    rs_length = st.number_input("RS Lookback Length", value=90, min_value=10)
    top_n = st.number_input("Top N for Group Avg", value=5, min_value=1)
    
    if st.button("Clear Cache & Refresh"):
        st.cache_data.clear()

# 4. IMPLEMENTATION OF NEW NORMALIZED RS METHOD AND EMA CLOUD
@st.cache_data(ttl=3600)
def get_rs_and_cloud_data_cached(tickers_tuple, benchmark_ticker, length): # <-- Added length parameter
    tickers = list(tickers_tuple)
    try:
        all_tickers = tickers + [benchmark_ticker]
        # Download data (ensuring enough historical data to compute the rolling min/max lookback window)
        data = yf.download(all_tickers, period="2y", interval="1d", progress=False)
        
        close_data = data['Close']
        high_data = data['High']
        low_data = data['Low']
        
        valid_tickers = [t for t in tickers if t in close_data.columns and close_data[t].notna().sum() >= length]
        if not valid_tickers: return None, None, None

        # --- New RS Logic ---
        bench_close = close_data[benchmark_ticker]
        stock_scores = {}
        cloud_tickers = []

        for ticker in valid_tickers:
            # 1. rsClose = close / indexClose
            rs_ratio_series = close_data[ticker] / bench_close
            
            # 2. hh = ta.highest(rsClose, length) | ll = ta.lowest(rsClose, length)
            # Use rolling window to get historical highs and lows of the ratio
            hh = rs_ratio_series.rolling(window=length).max()
            ll = rs_ratio_series.rolling(window=length).min()
            
            # Get the absolute most recent values (today's values)
            current_rs = rs_ratio_series.iloc[-1]
            current_hh = hh.iloc[-1]
            current_ll = ll.iloc[-1]
            
            # 3. Normalized logic: ((99 - 1) * (rsClose - ll) / (hh - ll)) + 1
            if pd.isna(current_hh) or pd.isna(current_ll) or current_hh == current_ll:
                total_score = 0
            else:
                # Convert the entire formula directly into an integer
                total_score = int(((99 - 1) * (current_rs - current_ll) / (current_hh - current_ll)) + 1)
            
            # This will now store a clean whole number (e.g., 85 instead of 85.34)
            stock_scores[ticker] = total_score

            # EMA Cloud Calculation (21 EMA of High/Low) - Kept Unchanged
            ema_low = low_data[ticker].ewm(span=21, adjust=False).mean().iloc[-1]
            ema_high = high_data[ticker].ewm(span=21, adjust=False).mean().iloc[-1]
            current_price = close_data[ticker].iloc[-1]
            
            if ema_low <= current_price <= ema_high:
                cloud_tickers.append(ticker)

        rs_perf = pd.Series(stock_scores).astype(int)
        
        # We assign the raw score directly as your ranking metrics instead of the old percentile conversion
        return rs_perf, rs_perf, cloud_tickers
    except Exception as e:
        st.error(f"Error: {e}")
        return None, None, None

# Reference Scanner Logic Functions
def scan_two_botak(df, lookback=0):
    idx = -1 - lookback
    if len(df) < abs(idx) + 1: return False
    botak = (
        (abs(df['Close'] - df['High']) < 0.05) & 
        (df['Close'] > df['Open'])
    )
    percentile = (
        (df['Close'] > df['Open']) & 
        (((df['Close'] - df['Open']) / ((df['High'] - df['Open']).replace(0, 0.001))) > 0.9)
    )
    twoBotak = (
        (botak & botak.shift(1)) |
        (botak & percentile.shift(1)) |
        (percentile & botak.shift(1)) |
        (percentile & percentile.shift(1))
    )
    return bool(twoBotak.iloc[idx])

def scan_engulfing(df, lookback=0):
    idx = -1 - lookback
    if len(df) < 30 + lookback: return False, False
    bullish_engulfing = (
        (df['Open'] < df['Low'].shift(1)) &
        (df['Close'] > df['High'].shift(1))
    )
    engulf_count_series = bullish_engulfing.rolling(window=30).sum()
    
    # Logic for historical comparison
    df_temp = df.iloc[:len(df)-lookback] if lookback > 0 else df
    current_idx = df_temp.index[-1]
    
    engulf_closes = df_temp.loc[bullish_engulfing, 'Close']
    prior_engulfs = engulf_closes[engulf_closes.index < current_idx]

    eng1 = prior_engulfs.iloc[-1] if len(prior_engulfs) >= 1 else 0
    eng2 = prior_engulfs.iloc[-2] if len(prior_engulfs) >= 2 else 0
    eng3 = prior_engulfs.iloc[-3] if len(prior_engulfs) >= 3 else 0

    current_close = df_temp['Close'].iloc[-1]
    current_count = engulf_count_series.iloc[idx]

    two_engulf = (
        (current_count >= 2) and
        (current_close > 20) and
        (current_close > eng1) and
        (current_close > eng2)
    )
    three_engulf = (
        (current_count >= 3) and
        (current_close > 20) and
        (current_close > eng1) and
        (current_close > eng2) and
        (current_close > eng3)
    )
    return bool(two_engulf), bool(three_engulf)

def scan_powertrend(df, lookback=0):
    idx = -1 - lookback
    if len(df) < 52 + lookback: return False
    powerma = df['Close'].ewm(span=50, adjust=False).mean()
    gradient = powerma - powerma.shift(1)
    gradientPct = ((powerma - powerma.shift(1)) / powerma.shift(1)) * 100
    absGradient = abs(gradientPct)
    powertrend = (
        (gradient > 0) &
        (absGradient >= 0.1) & 
        (df['Close'] >= 20)
    )
    return bool(powertrend.iloc[idx])

def scan_powertrend_not_extended(df, lookback=0):
    idx = -1 - lookback
    if len(df) < 52 + lookback: return False
    powerma = df['Close'].ewm(span=50, adjust=False).mean()
    gradient = powerma - powerma.shift(1)
    gradientPct = ((powerma - powerma.shift(1)) / powerma.shift(1)) * 100
    absGradient = abs(gradientPct)
    
    powertrend = (
        (gradient > 0) &
        (absGradient >= 0.1) &
        (df['Close'] >= 20)
    )

    high_low = df['High'] - df['Low']
    high_close = abs(df['High'] - df['Close'].shift(1))
    low_close = abs(df['Low'] - df['Close'].shift(1))
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    absATR = tr.rolling(14).mean()
    atrPercent = (absATR / df['Close']) * 100
    sma50 = df['Close'].rolling(50).mean()
    percentGainFromMA = ((df['Close'] - sma50) / sma50) * 100
    atrMultiple2 = percentGainFromMA / atrPercent.replace(0, 0.001)
    atrMultiple = (atrMultiple2 * 10).fillna(0).astype(int) / 10

    result = (powertrend & (atrMultiple <= 4))
    return bool(result.iloc[idx])

def scan_ppp(df, lookback=0):
    idx = -1 - lookback
    if len(df) < 200 + lookback: return False
    high_low = df['High'] - df['Low']
    high_close = abs(df['High'] - df['Close'].shift(1))
    low_close = abs(df['Low'] - df['Close'].shift(1))
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    myAtr = tr.rolling(14).mean()
    myAtr3 = myAtr / df['Close'] * 100
    dynamicSensitivity = myAtr3 * 0.2

    day0 = (df['Open'] + df['Close']) / 2
    day1 = day0.shift(1)
    day2 = day0.shift(2)

    diff0 = abs((day0 - day1) / day1.replace(0, 0.001) * 100)
    diff1 = abs((day1 - day2) / day2.replace(0, 0.001) * 100)

    sma50 = df['Close'].rolling(50).mean()
    sma200 = df['Close'].rolling(200).mean()

    ma21_and_ma50_or_ma200 = (
        (
            ((df['Close'] >= sma200) & (df['Close'] >= sma50))
        ) &
        (df['Close'] >= 20)
    )

    ppp = (
        (diff0 < dynamicSensitivity) &
        (diff1 < dynamicSensitivity) &
        ma21_and_ma50_or_ma200
    )
    return bool(ppp.iloc[idx])

@st.cache_data(ttl=3600)
def process_pattern_scanners(stocks_list):
    try:
        raw_data = yf.download(stocks_list, period="1y", interval="1d", progress=False)
        
        # Today's Matches
        botak_matches = []
        engulf2_matches = []
        engulf3_matches = []
        powertrend_matches = []
        powertrend_ne_matches = []
        ppp_matches = []
        
        # Yesterday's Matches (for color logic)
        botak_yest = []
        engulf2_yest = []
        engulf3_yest = []
        powertrend_yest = []
        powertrend_ne_yest = []
        ppp_yest = []
        
        for ticker in stocks_list:
            try:
                if len(stocks_list) > 1:
                    ticker_df = pd.DataFrame({
                        'Open': raw_data['Open'][ticker],
                        'High': raw_data['High'][ticker],
                        'Low': raw_data['Low'][ticker],
                        'Close': raw_data['Close'][ticker]
                    }).dropna()
                else:
                    ticker_df = raw_data.dropna()
                
                if ticker_df.empty or len(ticker_df) < 50:
                    continue
                
                # Scan Today
                if scan_two_botak(ticker_df, 0): botak_matches.append(ticker)
                e2, e3 = scan_engulfing(ticker_df, 0)
                if e2: engulf2_matches.append(ticker)
                if e3: engulf3_matches.append(ticker)
                if scan_powertrend(ticker_df, 0): powertrend_matches.append(ticker)
                if scan_powertrend_not_extended(ticker_df, 0): powertrend_ne_matches.append(ticker)
                if scan_ppp(ticker_df, 0): ppp_matches.append(ticker)

                # Scan Yesterday
                if scan_two_botak(ticker_df, 1): botak_yest.append(ticker)
                e2y, e3y = scan_engulfing(ticker_df, 1)
                if e2y: engulf2_yest.append(ticker)
                if e3y: engulf3_yest.append(ticker)
                if scan_powertrend(ticker_df, 1): powertrend_yest.append(ticker)
                if scan_powertrend_not_extended(ticker_df, 1): powertrend_ne_yest.append(ticker)
                if scan_ppp(ticker_df, 1): ppp_yest.append(ticker)

            except:
                continue
                
        botak_matches.sort()
        engulf2_matches.sort()
        engulf3_matches.sort()
        powertrend_matches.sort()
        powertrend_ne_matches.sort()
        ppp_matches.sort()
        
        return (botak_matches, engulf2_matches, engulf3_matches, powertrend_matches, powertrend_ne_matches, ppp_matches,
                botak_yest, engulf2_yest, engulf3_yest, powertrend_yest, powertrend_ne_yest, ppp_yest)
    except:
        return [], [], [], [], [], [], [], [], [], [], [], []

# 5. UI Layout & Logic
st.markdown("<h3 style='font-size: 16px; margin-bottom: 10px;'>📊 Relative Strength Screener</h3>", unsafe_allow_html=True)

all_data = []
progress_bar = st.progress(0)
status_text = st.empty()

industry_items = list(INDUSTRIES.items())
for idx, (industry_name, tickers) in enumerate(industry_items):
    status_text.text(f"Processing {industry_name}...")
    perf, rs_scores, cloud_list = get_rs_and_cloud_data_cached(tuple(tickers), benchmark, 90)
    
    if rs_scores is not None:
        top_n_scores = rs_scores.nlargest(int(top_n))
        group_avg = top_n_scores.mean()
        df_tickers = pd.DataFrame({"Ticker": rs_scores.index, "RS Score": rs_scores.values}).sort_values(by="RS Score", ascending=False)
        all_data.append({
            "Industry": industry_name, 
            "Group RS": group_avg, 
            "Tickers": df_tickers, 
            "Cloud": cloud_list
        })
    
    progress_bar.progress((idx + 1) / len(industry_items))

status_text.empty()
progress_bar.empty()

# 6. Compact Display Logic
if all_data:
    df_main = pd.DataFrame([{"Industry": item["Industry"], "Group RS": item["Group RS"]} for item in all_data])

    col1, col2 = st.columns([1, 1])
    with col1:
        sort_by = st.selectbox("Sort by", ["Group RS (High to Low)", "Industry (A-Z)", "Group RS (Low to High)"])
    with col2:
        sort_order = st.radio("Order", ["Descending", "Ascending"], horizontal=True)

    if "Industry" in sort_by:
        df_main = df_main.sort_values("Industry", ascending=(sort_order == "Ascending"))
    else:
        df_main = df_main.sort_values("Group RS", ascending=(sort_order == "Ascending"))

    st.markdown("""
    <style>
    .ticker-badge { 
        display: inline-block; 
        margin: 1px 3px; 
        padding: 1px 5px; 
        border: 1px solid #444; 
        border-radius: 3px; 
        font-size: 11px; 
        background-color: #1e1e1e; 
        color: #eee; 
        white-space: nowrap;
    }
    .cloud-badge {
        background-color: #2e4a3e;
        border: 1px solid #4ecdc4;
    }
    .pattern-badge {
        background-color: #1f3a52;
        border: 1px solid #3a86c8;
        color: #fff;
        font-weight: bold;
    }
    .new-pattern-badge {
        background-color: #FFD700;
        border: 1px solid #B8860B;
        color: #000;
        font-weight: bold;
    }
    .ticker-name { font-weight: bold; color: #ffffff; margin-right: 4px; }
    .ticker-rs { color: #4ecdc4; font-weight: normal; }
    table { width:100%; border-collapse: collapse; }
    th { padding: 4px 8px !important; background-color: #1f77b4; color: white; font-size: 12px; }
    td { padding: 2px 8px !important; border-bottom: 1px solid #333; font-size: 12px; }
    </style>
    """, unsafe_allow_html=True)

    table_html = """<table>
    <thead><tr>
    <th style="text-align: center; width: 40px;">#</th>
    <th style="text-align: left;">Industry</th>
    <th style="text-align: center; width: 80px;">Group RS</th>
    <th style="text-align: left;">Tickers (Ranked)</th>
    <th style="text-align: left; width: 150px;">Within 21 EMA Cloud</th>
    </tr></thead><tbody>"""

    for row_num, (i, row) in enumerate(df_main.iterrows(), start=1):
        item = next(d for d in all_data if d["Industry"] == row["Industry"])
        # Change :.1f to :.0f right here:
        ticker_html = "".join([f'<div class="ticker-badge"><span class="ticker-name">{r["Ticker"]}</span><span class="ticker-rs">{r["RS Score"]:.0f}</span></div>' for _, r in item["Tickers"].iterrows()])
        
        cloud_html = "".join([f'<div class="ticker-badge cloud-badge">{c}</div>' for c in item["Cloud"]])
        bg_color = "#262730" if row_num % 2 == 0 else "#0e1117"
        
        table_html += f"""<tr style="background-color: {bg_color};">
        <td style="text-align: center; color: #888; font-weight: bold;">{row_num}</td>
        <td style="font-weight: bold;">{row['Industry']}</td>
        <td style="text-align: center; color: #4ecdc4; font-weight: bold;">{row['Group RS']:.1f}</td>
        <td>{ticker_html}</td>
        <td>{cloud_html}</td></tr>"""

    table_html += "</tbody></table>"
    st.markdown(table_html, unsafe_allow_html=True)

# 7. EXTRA SEPARATE PATTERNS SCANNING BLOCK
st.markdown("---")
st.markdown("### 🔍 Technical Pattern Screener (KNOWN_STOCKS Database)")

with st.spinner("Scanning pattern anomalies across known instruments..."):
    results = process_pattern_scanners(tuple(KNOWN_STOCKS))
    b_list, e2_list, e3_list, pt_list, ptne_list, ppp_list = results[:6]
    b_yest, e2_yest, e3_yest, pt_yest, ptne_yest, ppp_yest = results[6:]

col_b, col_p, col_e = st.columns(3)

with col_b:
    # --- Added bracket count here ---
    st.subheader(f"🔥 Two Botak ({len(b_list)})")
    if b_list:
        html_b = ""
        for sym in b_list:
            cls = "new-pattern-badge" if sym not in b_yest else "pattern-badge"
            html_b += f'<div class="ticker-badge {cls}">{sym}</div>'
        st.markdown(html_b, unsafe_allow_html=True)
    else:
        st.info("No active setups discovered.")

with col_p:
    # --- Added bracket count here ---
    st.subheader(f"📈 Tight PPP ({len(ppp_list)})")
    if ppp_list:
        html_p = ""
        for sym in ppp_list:
            cls = "new-pattern-badge" if sym not in ppp_yest else "pattern-badge"
            html_p += f'<div class="ticker-badge {cls}">{sym}</div>'
        st.markdown(html_p, unsafe_allow_html=True)
    else:
        st.info("No active setups discovered.")

with col_e:
    # Total count for all engulfing combined in the header
    total_engulf = len(e2_list) + len(e3_list)
    st.subheader(f"🐳 Bullish Engulfing ({total_engulf})")
    
    if e2_list or e3_list:
        if e2_list:
            # --- Added bracket count here ---
            st.markdown(f"**2x Engulfing Conditions Matched ({len(e2_list)}):**")
            html_e2 = ""
            for sym in e2_list:
                cls = "new-pattern-badge" if sym not in e2_yest else "pattern-badge"
                html_e2 += f'<div class="ticker-badge {cls}">{sym}</div>'
            st.markdown(html_e2, unsafe_allow_html=True)
        if e3_list:
            # --- Added bracket count here ---
            st.markdown(f"<div style='margin-top:10px;'><b>3x Engulfing Conditions Matched ({len(e3_list)}):</b></div>", unsafe_allow_html=True)
            html_e3 = ""
            for sym in e3_list:
                cls = "new-pattern-badge" if sym not in e3_yest else "pattern-badge"
                html_e3 += f'<div class="ticker-badge {cls}">{sym}</div>'
            st.markdown(html_e3, unsafe_allow_html=True)
    else:
        st.info("No active setups discovered.")

with st.expander("Show Extra Trend Metrics (PowerTrend Indicators)"):
    col_pt1, col_pt2 = st.columns(2)
    with col_pt1:
        # --- Added bracket count here ---
        st.markdown(f"**PowerTrend ({len(pt_list)}):**")
        if pt_list:
            html_pt = ""
            for sym in pt_list:
                cls = "new-pattern-badge" if sym not in pt_yest else ""
                html_pt += f'<div class="ticker-badge {cls}">{sym}</div>'
            st.markdown(html_pt, unsafe_allow_html=True)
        else:
            st.text("None")
            
    with col_pt2:
        # --- Added bracket count here ---
        st.markdown(f"**PowerTrend Not Extended ({len(ptne_list)}):**")
        if ptne_list:
            html_ptne = ""
            for sym in ptne_list:
                cls = "new-pattern-badge" if sym not in ptne_yest else "cloud-badge"
                html_ptne += f'<div class="ticker-badge {cls}">{sym}</div>'
            st.markdown(html_ptne, unsafe_allow_html=True)
        else:
            st.text("None")