# SGC Glyph Console 1.0

## Cosa cambia

Questa versione riparte dalla **SGC Glyph Input Console 0.5**: la pagina `preview.html` conserva il motore d'inserimento, la mappatura italiana, il parser dei codici vettoriali, il blocco dei duplicati e il test Abydos. È stato aggiunto il comando **DIALING**, che si abilita solo con sei coordinate valide e apre una seconda pagina dedicata.

La pagina `dialing.html` ricrea il monitor operativo SGC durante la composizione. Non mostra una pianta della Gate Room né una veduta architettonica: è una grafica da monitor, con anello circolare, simboli, chevron, circuiti, lista verticale dei sette simboli e indicatori di stato.

## Avvio

1. Estrai l'intero ZIP in una cartella, ad esempio `Downloads\SGC_Glyph_Console_v1.0`.
2. Apri `preview.html` oppure esegui `AVVIA_SGC.ps1` con PowerShell.
3. Seleziona `CODICE VETTORIALE` e premi `PROVA ABYDOS`, oppure inserisci sei glifi con la tastiera italiana.
4. Quando il contatore raggiunge `6 / 6`, premi **DIALING**.
5. Si apre automaticamente `dialing.html`, che avvia l'animazione. Il pulsante `BACK TO INPUT` riporta alla pagina precedente conservando l'indirizzo.

## Font SGC Glyph

Il CSS prova prima a utilizzare il font Windows installato (`local('SGC Glyph')`). Se il browser non lo trova, copia dalla precedente cartella `output` questi file, se disponibili, nella cartella `output` di questo progetto:

- `SGC_Glyph.ttf`
- `SGC_Glyph.woff2`

Il pacchetto non include il font generato sul PC dell'utente perché non è disponibile nell'ambiente di preparazione.

## Regole mantenute dalla v0.5

- Sei glifi di destinazione.
- Nessun glifo duplicato.
- Il vettore `01` è riservato al punto d'origine terrestre e viene aggiunto come settimo simbolo.
- Il codice `27-07-15-32-12-30` viene letto come sei identificativi completi, non come singole cifre.
- Il tasto fisico e la tastiera virtuale continuano a usare la mappatura italiana.

## Correzione animazione nella 0.9

La 0.8 aveva un errore nel sistema di coordinate: la posizione dei glifi era calcolata con asse Y SVG positivo verso il basso, mentre la posizione dei chevron era definita con asse Y invertito. Il risultato poteva far ruotare il simbolo verso il lato opposto del quadrante. La 0.9 converte correttamente l’angolo del chevron nel sistema SVG e sceglie la posizione angolare equivalente più vicina, evitando rotazioni inutilmente lunghe. Il glifo di origine 01, destinato al chevron superiore, resta quindi allineato in alto senza una rotazione di 180°. Sono stati aggiunti anche impulsi brevi al momento del blocco dei chevron e delle caselle risultato.

## Animazione della seconda schermata

Premendo `DIALING`, il sistema riceve i sei vettori già validati e aggiunge il vettore d'origine `01`. La seconda schermata:

1. ruota l'anello dei glifi verso il chevron interessato;
2. evidenzia il chevron e il relativo circuito;
3. mostra il glifo centrale e lo trasferisce nella casella numerata a destra;
4. aggiorna la lista e il controllo `OK`;
5. al settimo simbolo cambia `SEQUENCE IN PROGRESS` in `SEQUENCE COMPLETE`.

La sequenza dei sette chevron è una ricostruzione animata ispirata ai fotogrammi e alle descrizioni delle schermate SGC della serie. Non contiene filmati, audio o risorse video della serie. È una fan recreation, non un'interfaccia ufficiale né una copia del software originale.

## Test di riferimento

Per Abydos l'input previsto è:

`27-07-15-32-12-30`

La sequenza completa visualizzata nella seconda pagina è:

`27 · 07 · 15 · 32 · 12 · 30 · 01`

## Riferimenti visivi e narrativi

- Schermata SGC di composizione: https://www.thestargatecommand.com/sg1_101_0311.jpeg
- Immagine della lista indirizzo / sette glifi: https://www.gateworld.net/wiki/images/3/3e/Address2.jpg
- Trascrizione dell'episodio "1969" (S02E21), che descrive il settimo glifo che entra nella sequenza a destra e il passaggio da `SEQUENCE IN PROGRESS` a `SEQUENCE COMPLETE`: https://www.stargate-sg1-solutions.com/wiki/2.21_%221969%22_Transcript

L'impostazione è stata disegnata in SVG/CSS/JavaScript per funzionare offline in Edge o Chrome. La geometria è una ricostruzione fan-made basata su riferimenti visivi pubblici; non è garantita una corrispondenza pixel-per-pixel con ogni variante di monitor mostrata nei diversi episodi.


## Correzione del fulcro dell'anello nella 1.0

Nella 0.9 l'animazione applicava la rotazione al gruppo SVG usando un angolo di rotazione attorno a coordinate globali, mentre era presente anche una regola CSS `transform-origin` espressa in pixel. A seconda del riferimento usato dal browser per l'elemento SVG, la combinazione poteva produrre un fulcro inatteso e dare l'impressione che l'anello oscillasse o facesse perno fuori dal proprio centro.

Nella 1.0 la regola CSS `transform-origin` è stata rimossa e la trasformazione è esplicitata nel sistema di coordinate SVG: `translate(cx cy) rotate(angle) translate(-cx -cy)`. Il fulcro è quindi fissato al centro del quadrante (743, 513) nello stesso viewBox del disegno. I pannelli, i chevron, il telaio e gli altri elementi restano fermi; ruota soltanto il gruppo dei glifi e delle tacche.
