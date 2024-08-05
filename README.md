# Clip Raster Plugin

Il **Clip Raster Plugin** è un plugin per QGIS che consente di ritagliare un raster utilizzando una geometria vettoriale. Questo plugin è utile per estrarre porzioni specifiche di un raster basate su geometrie definite in un layer vettoriale.

## Funzionalità

- Selezione di layer raster e vettoriali dal progetto QGIS corrente.
- Specifica della cartella di output per i raster ritagliati.
- Barra di progresso per monitorare l'avanzamento del processo di ritaglio.
- Aggiunta automatica dei raster ritagliati al progetto QGIS.

## Installazione

1. Copia la cartella del plugin nella directory dei plugin di QGIS:

2. Riavvia QGIS.

3. Attiva il plugin tramite il menu `Plugins` > `Manage and Install Plugins...`.

## Utilizzo

1. Apri QGIS e carica i layer raster e vettoriali che desideri utilizzare.

2. Avvia il plugin dal menu `Plugins` > `Clip Raster Plugin`.

3. Nella finestra di dialogo del plugin:
   - Seleziona il layer vettoriale contenente le geometrie di ritaglio.
   - Seleziona il layer raster da ritagliare.
   - Specifica la cartella di output dove verranno salvati i raster ritagliati.
   - (Opzionale) Seleziona l'opzione per aggiungere automaticamente i raster ritagliati al progetto QGIS.

4. Clicca su `OK` per avviare il processo di ritaglio.

5. Monitora l'avanzamento tramite la barra di progresso.

6. Al termine, i raster ritagliati saranno salvati nella cartella di output specificata e, se selezionato, aggiunti al progetto QGIS.

## Requisiti

- QGIS 3.x
- PyQt5

## Contributi

I contributi sono benvenuti! Sentiti libero di fare fork del repository e inviare pull request.

## Licenza

Questo progetto è distribuito sotto la licenza Creative Commons Attribution 4.0 International (CC BY 4.0). Vedi il file [LICENSE](LICENSE) per maggiori dettagli.

## Contatti

Per domande o supporto, contatta enzo cocca all'indirizzo enzo.ccc@gmail.com.

