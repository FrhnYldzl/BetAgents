"""Calculates implied probabilities and pick signals from iddaa live matches."""
import sys
sys.path.insert(0, "02_VERI")

matches = [
    {"id":"2903417","date":"29 May Cts 17:15","home":"Al Urooba UAE","away":"Masfoot SC","o1":1.29,"oX":3.99,"o2":6.09,"ou":1.48,"uu":1.93,"ky":1.67,"kn":1.69,"lig":"BAE Ligi"},
    {"id":"2977789","date":"29 May Cts 22:00","home":"Real Madrid Castilla","away":"CE Sabadell","o1":2.0,"oX":2.97,"o2":2.8,"ou":1.86,"uu":1.53,"ky":1.67,"kn":1.69,"lig":"Ispanya 3. Lig"},
    {"id":"2903586","date":"30 May Paz 10:30","home":"NWS Spirit","away":"Apia Leic","o1":3.28,"oX":3.61,"o2":1.63,"ou":None,"uu":None,"ky":1.33,"kn":2.26,"lig":"Avustralya"},
    {"id":"2972160","date":"30 May Paz 14:00","home":"Taborsko","away":"Banik Ostrava","o1":4.33,"oX":3.48,"o2":1.48,"ou":1.64,"uu":1.71,"ky":1.66,"kn":1.70,"lig":"Cek Cumhuriyeti"},
    {"id":"2939931","date":"30 May Paz 14:00","home":"FK Arsenal Dzerzhinsk","away":"Dinamo Minsk","o1":9.72,"oX":3.84,"o2":1.21,"ou":1.72,"uu":1.63,"ky":2.15,"kn":1.38,"lig":"Belarus"},
    {"id":"2902699","date":"30 May Paz 15:30","home":"Hutnik Krakow","away":"S. Stalowa","o1":2.75,"oX":3.19,"o2":1.93,"ou":1.54,"uu":1.85,"ky":1.45,"kn":1.99,"lig":"Polonya"},
    {"id":"2902748","date":"30 May Paz 15:30","home":"LKS Lodz II","away":"Sokol Kleczew","o1":3.23,"oX":3.82,"o2":1.61,"ou":1.38,"uu":2.12,"ky":1.39,"kn":2.09,"lig":"Polonya"},
    {"id":"2976696","date":"30 May Paz 16:00","home":"R Montevideo","away":"Defensor Sporting","o1":1.75,"oX":2.96,"o2":3.53,"ou":2.17,"uu":1.36,"ky":1.95,"kn":1.46,"lig":"Uruguay"},
    {"id":"2939932","date":"30 May Paz 16:00","home":"Neman Grodno","away":"Maxline Rogachev","o1":4.54,"oX":3.20,"o2":1.51,"ou":1.76,"uu":1.60,"ky":1.73,"kn":1.62,"lig":"Belarus"},
    {"id":"2939920","date":"30 May Paz 16:00","home":"FC Gomel","away":"Dinamo Brest","o1":2.31,"oX":2.73,"o2":2.53,"ou":1.95,"uu":1.46,"ky":1.68,"kn":1.67,"lig":"Belarus"},
    {"id":"2943192","date":"30 May Paz 19:00","home":"Tarma","away":"Cusco FC","o1":1.94,"oX":2.93,"o2":2.96,"ou":1.57,"uu":1.78,"ky":1.45,"kn":1.98,"lig":"Peru"},
    {"id":"2976704","date":"30 May Paz 21:00","home":"Danubio FC","away":"CA Progreso","o1":1.80,"oX":2.96,"o2":3.32,"ou":2.00,"uu":1.44,"ky":1.80,"kn":1.56,"lig":"Uruguay"},
    {"id":"2957009","date":"30 May Paz 21:30","home":"Gimnasia Jujuy","away":"Belgrano","o1":3.33,"oX":2.60,"o2":1.96,"ou":None,"uu":None,"ky":1.98,"kn":1.46,"lig":"Arjantin"},
    {"id":"2961823","date":"30 May Paz 22:30","home":"CF Belenenses","away":"Sporting Farense","o1":2.43,"oX":2.86,"o2":2.32,"ou":1.93,"uu":1.48,"ky":1.69,"kn":1.66,"lig":"Portekiz"},
    {"id":"2943189","date":"30 May Paz 23:00","home":"Dep. Garcilaso","away":"Juan Pablo II","o1":1.41,"oX":3.71,"o2":4.65,"ou":1.50,"uu":1.90,"ky":1.57,"kn":1.79,"lig":"Peru"},
    {"id":"2957015","date":"31 May Pts 00:00","home":"Instituto AC Cordoba","away":"Ath Lanus","o1":2.37,"oX":2.72,"o2":2.47,"ou":None,"uu":None,"ky":1.90,"kn":1.50,"lig":"Arjantin"},
    {"id":"2943168","date":"31 May Pts 01:30","home":"Sport Boys","away":"Com. Unidos","o1":1.47,"oX":3.32,"o2":4.69,"ou":1.88,"uu":1.51,"ky":1.87,"kn":1.52,"lig":"Peru"},
    {"id":"2966375","date":"31 May Pts 04:00","home":"Tampico Madero","away":"Tepatitlan FC","o1":1.90,"oX":2.80,"o2":3.21,"ou":1.89,"uu":1.51,"ky":1.67,"kn":1.68,"lig":"Meksika"},
    {"id":"2952046","date":"31 May Pts 04:00","home":"Guney Kore","away":"Trinidad-Tobago","o1":1.00,"oX":7.23,"o2":17.75,"ou":None,"uu":None,"ky":None,"kn":None,"lig":"Uluslararasi"},
    {"id":"2943165","date":"31 May Pts 04:00","home":"U. Deportes","away":"Huancayo","o1":1.16,"oX":4.73,"o2":7.94,"ou":1.46,"uu":1.95,"ky":1.84,"kn":1.54,"lig":"Peru"},
    {"id":"2905706","date":"31 May Pts 11:00","home":"Olympic FC","away":"Brisbane City","o1":1.99,"oX":3.57,"o2":2.43,"ou":None,"uu":None,"ky":1.22,"kn":2.68,"lig":"Avustralya"},
    {"id":"2976699","date":"31 May Pts 16:00","home":"Albion FC","away":"Torque","o1":2.41,"oX":2.88,"o2":2.31,"ou":1.87,"uu":1.51,"ky":1.65,"kn":1.70,"lig":"Uruguay"},
    {"id":"2939919","date":"31 May Pts 16:00","home":"Slavia Mozyr","away":"FC Belshina","o1":1.31,"oX":3.96,"o2":5.62,"ou":1.67,"uu":1.68,"ky":1.85,"kn":1.54,"lig":"Belarus"},
    {"id":"2953644","date":"31 May Pts 17:00","home":"Cekya","away":"Kosova","o1":1.51,"oX":3.49,"o2":4.76,"ou":1.78,"uu":1.66,"ky":1.79,"kn":1.66,"lig":"Uluslararasi"},
    {"id":"2977846","date":"31 May Pts 17:15","home":"CE Europa","away":"Celta Vigo B","o1":2.19,"oX":2.80,"o2":2.64,"ou":1.96,"uu":1.46,"ky":1.70,"kn":1.64,"lig":"Ispanya 3. Lig"},
    {"id":"2964680","date":"31 May Pts 20:30","home":"Farul Cons.","away":"Chindia","o1":1.30,"oX":3.86,"o2":6.15,"ou":1.67,"uu":1.68,"ky":1.86,"kn":1.52,"lig":"Romanya"},
    {"id":"2976703","date":"31 May Pts 21:00","home":"CA Juventud","away":"Montevideo City","o1":1.99,"oX":2.91,"o2":2.88,"ou":1.86,"uu":1.52,"ky":1.66,"kn":1.69,"lig":"Uruguay"},
    {"id":"2943159","date":"31 May Pts 23:15","home":"Los Chankas","away":"Cajamarca","o1":1.54,"oX":3.31,"o2":4.13,"ou":1.63,"uu":1.72,"ky":1.61,"kn":1.74,"lig":"Peru"},
    {"id":"2964689","date":"01 Haz Pts 20:30","home":"Voluntari","away":"Hermannstadt","o1":2.43,"oX":2.82,"o2":2.33,"ou":1.91,"uu":1.49,"ky":1.67,"kn":1.69,"lig":"Romanya"},
    {"id":"2976702","date":"01 Haz Pts 21:00","home":"Boston River","away":"Liverpool Montevideo","o1":2.94,"oX":2.93,"o2":1.95,"ou":1.92,"uu":1.49,"ky":1.70,"kn":1.64,"lig":"Uruguay"},
]

def fp(o):
    return 1/o if o else None

def true_probs(o1, oX, o2):
    if not (o1 and oX and o2): return None,None,None
    vig = 1/o1 + 1/oX + 1/o2
    return round((1/o1)/vig, 3), round((1/oX)/vig, 3), round((1/o2)/vig, 3)

def ou_probs(ou, uu):
    if not (ou and uu): return None, None
    vig = 1/ou + 1/uu
    return round((1/ou)/vig, 3), round((1/uu)/vig, 3)

def kg_probs(ky, kn):
    if not (ky and kn): return None, None
    vig = 1/ky + 1/kn
    return round((1/ky)/vig, 3), round((1/kn)/vig, 3)

strong_picks = []

for m in matches:
    p1, pX, p2 = true_probs(m["o1"], m["oX"], m["o2"])
    pou, puu = ou_probs(m.get("ou"), m.get("uu"))
    pky, pkn = kg_probs(m.get("ky"), m.get("kn"))
    m.update({"p1":p1,"pX":pX,"p2":p2,"pou":pou,"puu":puu,"pky":pky,"pkn":pkn})

    signals = []
    if p1 and p1 >= 0.65: signals.append(("1", m["o1"], "GUCLU EV FAVORISI"))
    elif p1 and p1 >= 0.58: signals.append(("1", m["o1"], "ev favorisi"))
    if p2 and p2 >= 0.65: signals.append(("2", m["o2"], "GUCLU DEPLASMAN FAVORISI"))
    elif p2 and p2 >= 0.58: signals.append(("2", m["o2"], "dep favorisi"))
    if pky and pky >= 0.58: signals.append(("KG Var", m["ky"], "KG Var sinyali"))
    if puu and puu >= 0.60: signals.append(("Alt 2.5", m["uu"], "Alt 2.5 sinyali"))
    if pou and pou >= 0.60: signals.append(("Ust 2.5", m["ou"], "Ust 2.5 sinyali"))
    m["signals"] = signals
    if signals:
        strong_picks.append(m)

# Print all
for m in matches:
    line = f"{m['date']} | {m['lig']}"
    line += f"\n  {m['home']} vs {m['away']}"
    line += f"\n  1: {m['o1']}({int(m['p1']*100) if m['p1'] else '-'}%)  X: {m['oX']}({int(m['pX']*100) if m['pX'] else '-'}%)  2: {m['o2']}({int(m['p2']*100) if m['p2'] else '-'}%)"
    if m["pou"] or m["puu"]:
        line += f"\n  Ust2.5: {m.get('ou','?')}({int(m['pou']*100) if m['pou'] else '-'}%)  Alt2.5: {m.get('uu','?')}({int(m['puu']*100) if m['puu'] else '-'}%)"
    if m["pky"]:
        line += f"\n  KG Var: {m.get('ky','?')}({int(m['pky']*100) if m['pky'] else '-'}%)  KG Yok: {m.get('kn','?')}({int(m['pkn']*100) if m['pkn'] else '-'}%)"
    if m["signals"]:
        sigs = " | ".join(f">> {s[0]} @ {s[1]} ({s[2]})" for s in m["signals"])
        line += f"\n  SINYAL: {sigs}"
    line += f"\n  IDDAA LINK: https://www.iddaa.com/program/futbol (EID:{m['id']})"
    print(line)
    print()

print("="*60)
print(f"TOPLAM SINYAL: {sum(len(m['signals']) for m in matches)} maçtan {len(strong_picks)}")
