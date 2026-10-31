# Memory Blog

## Random notes

Some sentences I like, sometimes in Dutch, sometimes in English.


Voor jouw ontwerp zou ik steeds vragen: *welk toekomstig gedrag moet dankzij deze herinnering veranderen?* Als daarop geen duidelijk antwoord bestaat, is opslaan misschien niet nodig.

Ik denk dat iets anders dat belangrijk is bij geheugen is dat de gebruiker in controle moet zijn. Natuurlijk kan een agent suggesties doen, maar de gebruiker moet de keuze hebben om ze te accepteren of niet. Het moet dus een dynamisch character hebben. Als je gewoon content hebt, dan past dit beter in een RAG oplossing. Geheugen kan hierbij helpen, maar ik zou voorkomen dat het een groeiende verzameling reparaties wordt voor structurele fouten in de kennisvoorziening.

Een bruikbaarder geheugenitem beschrijft:
- Situatie: actuele vragen over onderwerp X bij klant Y.
- Les: begin bij de geldende versie van document B.
- Reden: document A beschrijft een eerdere situatie.
- Uitzondering: bij historische vragen kan A juist relevant zijn.
- Bewijs: verwijzing naar de correctie en de documenten.
- Herziening: opnieuw beoordelen als B wordt vervangen.

Het is belangrijk om te realiseren wanneer je geheugen moet toepassen. Doe je dit keer op keer, een keer in de systeem prompt, voor een zoek actie als je deze wil optimaliseren. Moet je misschien opnieuw zoeken naar een gehuegen item als reacite op een zoek actie.

Een werkbare levenscyclus is:
1. Signaleren: er is een correctie, besluit, voorkeur of betekenisvolle uitkomst.
2. Vastleggen: bewaren wat daadwerkelijk is gezegd of vastgesteld.
3. Interpreteren: bepalen welke les daar mogelijk uit volgt.
4. Begrenzen: vaststellen voor wie en wanneer die les geldt.
5. Samenvoegen: bestaande herinneringen aanvullen, vervangen of tegenspreken.
6. Evalueren: nagaan of toepassing daadwerkelijk helpt.
7. Herzien of vergeten: verouderde en onbruikbare herinneringen uit gebruik nemen.

Ook zou ik opgehaalde herinneringen niet automatisch dezelfde autoriteit geven als vaste systeeminstructies. Een herinnering kan een onzekere conclusie of verouderde afspraak bevatten. De status moet zichtbaar blijven.

Wel interessant idee, vaak is geheugen gekoppeld aan een actie. Denk aan veranderen zoektermen, aanpassen naam, etc. Dan kun je dit ook meenemen in de actie  zelf, zonder dat de agent hier concreet iets mee hoeft te doen

!! Het idee van episodes en zelf lerende systemen vind ik wel nog steeds interessant. Hebben natuurlijk ook al eens naar prompt optimalisaties gekeken met DSPy. Maar geen idee of dat hier nog zou kunnen helpen.

