"""Crea las notas de «datos rápidos»: parentescos y nombres reales, en forma de pregunta y respuesta.

Son las preguntas cerradas que más se repiten («¿quién es la esposa de Tony Stark?», «¿cuál es el
nombre real de Hulk?»). Al estar escritas como pregunta, M-Jarvis las contesta al instante y con el
dato exacto, sin pasar por el modelo.

Uso (en la Latitude): python3 datos_rapidos.py ~/mjarvis/conocimiento/datos-rapidos
"""
import re
import shutil
import sys
from pathlib import Path

PARENTESCOS = """
la esposa de Tony Stark | Pepper Potts. Empezó como su asistente, dirigió Stark Industries y se casó con él; tienen una hija, [[Morgan Stark]].
la hija de Tony Stark | Morgan Stark, hija de Tony y de Pepper Potts. Es la niña que le dice «te quiero tres mil».
el padre de Tony Stark | Howard Stark, inventor y fundador de Stark Industries. Su madre fue Maria Stark. A los dos los mató el Soldado de Invierno en 1991.
el padre de Thor | Odín, rey de Asgard. Su madre es Frigga.
el hermano de Thor | Loki, su hermano adoptivo. Thor tiene además una hermana mayor, Hela, la diosa de la muerte.
la hermana de Thor | Hela, la diosa de la muerte, hija mayor de Odín.
el padre de Loki | Su padre biológico es Laufey, rey de los gigantes de hielo, pero lo adoptó y lo crió Odín.
la novia de Thor | Jane Foster, astrofísica. En Thor: Amor y trueno ella misma llega a ser la Poderosa Thor.
el padre de Star-Lord | Ego, un Celestial que es un planeta viviente. A Peter Quill lo crió Yondu, el jefe de los Saqueadores. Su madre fue Meredith Quill.
la hija de Thanos | Thanos tiene dos hijas adoptivas, Gamora y Nebula.
el padre de Gamora | Thanos, que la adoptó de niña tras arrasar su planeta. Su hermana adoptiva es Nebula.
la esposa de Ojo de Halcón | Laura Barton. Tienen tres hijos: Cooper, Lila y Nathaniel.
la novia de Spider-Man | MJ, Michelle Jones-Watson. Tras el hechizo de Sin camino a casa, ella ya no lo recuerda.
la tía de Spider-Man | May Parker, que lo crió. Muere a manos del Duende Verde en Spider-Man: Sin camino a casa.
el mejor amigo de Spider-Man | Ned Leeds, su compañero de escuela.
la hermana de Pantera Negra | Shuri, princesa e inventora de Wakanda. Tras la muerte de T'Challa, ella es la nueva Pantera Negra.
el padre de Pantera Negra | T'Chaka, rey de Wakanda, muerto en el atentado de Viena. Su madre es la reina Ramonda.
el hijo de Pantera Negra | Toussaint, hijo de T'Challa y de Nakia, que crece en Haití. Su nombre wakandiano es T'Challa.
la novia del Capitán América | Peggy Carter, agente británica de los años cuarenta. Al final de Vengadores: Endgame, Steve vuelve al pasado para vivir con ella.
el mejor amigo del Capitán América | Bucky Barnes, su amigo de la infancia, que fue el Soldado de Invierno. Hoy también lo es Sam Wilson.
el hermano de Wanda | Pietro Maximoff, Quicksilver, su hermano gemelo. Muere en Vengadores: La era de Ultrón.
la pareja de Wanda | Visión. Con él tuvo, dentro del Hex de Westview, a los gemelos Billy y Tommy.
los hijos de Wanda | Billy y Tommy, gemelos creados por su magia en WandaVision.
la hija de Ant-Man | Cassie Lang, hija de Scott Lang y de su exesposa Maggie.
la pareja de Ant-Man | Hope van Dyne, la Avispa.
los padres de la Avispa | Hank Pym, el primer Ant-Man, y Janet van Dyne, la primera Avispa.
la hermana de la Viuda Negra | Yelena Belova, su hermana adoptiva, criada con ella en la Sala Roja.
la esposa de Kingpin | Vanessa Fisk, de soltera Marianna. Muere en la temporada 2 de Daredevil: Born Again.
la madre de Daredevil | La hermana Maggie, una monja del orfanato donde creció. Su padre fue el boxeador Jack Murdock.
el hijo de Hulk | Skaar, nacido en el planeta Sakaar. Bruce Banner lo presenta al final de She-Hulk.
la prima de Hulk | Jennifer Walters, abogada, que se convierte en She-Hulk al recibir su sangre.
el padre de Shang-Chi | Xu Wenwu, el dueño de los Diez Anillos. Su madre fue Ying Li y su hermana es Xialing.
la esposa de Punisher | Maria Castle. Ella y sus dos hijos, Lisa y Frank Jr., murieron en un tiroteo; por eso Frank Castle se convirtió en Punisher.
la hermana de Jessica Jones | Trish Walker, su hermana adoptiva.
los padres de Franklin Richards | Reed Richards y Sue Storm, de los Cuatro Fantásticos.
el hermano de Sue Storm | Johnny Storm, la Antorcha Humana.
la hermana de Gamora | Nebula, también hija adoptiva de Thanos.
la hermana de Star-Lord | Mantis: los dos son hijos de Ego.
"""

NOMBRES = """
Iron Man | Tony Stark
Capitán América | Steve Rogers. Desde 2024 el Capitán América es Sam Wilson
Thor | Thor Odinson; no usa otro nombre
Hulk | Bruce Banner
Viuda Negra | Natasha Romanoff. Tras su muerte, su hermana Yelena Belova también usa el nombre
Ojo de Halcón | Clint Barton
Spider-Man | Peter Parker
Pantera Negra | T'Challa. Desde su muerte, la Pantera Negra es su hermana Shuri
Doctor Strange | Stephen Strange
Ant-Man | Scott Lang. El primero fue Hank Pym
Avispa | Hope van Dyne. La primera fue su madre, Janet van Dyne
Star-Lord | Peter Quill
Bruja Escarlata | Wanda Maximoff
Soldado de Invierno | Bucky Barnes, James Buchanan Barnes
Falcon | Sam Wilson. Desde que Sam es el Capitán América, Falcon es Joaquín Torres
Máquina de Guerra | James Rhodes, «Rhodey»
Capitana Marvel | Carol Danvers
Daredevil | Matt Murdock
Punisher | Frank Castle
Kingpin | Wilson Fisk
Bullseye | Benjamin Poindexter, «Dex»
Ms. Marvel | Kamala Khan
Moon Knight | Marc Spector, que comparte cuerpo con Steven Grant y Jake Lockley
She-Hulk | Jennifer Walters
Deadpool | Wade Wilson
Wolverine | Logan, cuyo nombre de nacimiento es James Howlett
Ironheart | Riri Williams
Echo | Maya Lopez
Guardián Rojo | Alexei Shostakov
U.S. Agent | John Walker
Fantasma | Ava Starr
El Centinela | Bob Reynolds
Mysterio | Quentin Beck
El Buitre | Adrian Toomes
Killmonger | Erik Stevens, de nombre wakandiano N'Jadaka
Cráneo Rojo | Johann Schmidt
Mister Fantástico | Reed Richards
Mujer Invisible | Sue Storm
Antorcha Humana | Johnny Storm
La Mole | Ben Grimm
Doctor Doom | Victor von Doom
Hulk Rojo | Thaddeus Ross
Wonder Man | Simon Williams
"""


GENERALES = """
Qué es el universo Marvel | El Universo Cinematográfico de Marvel es un conjunto de películas y series de Marvel Studios que cuentan una sola historia compartida, empezada en 2008 con Iron Man. Se divide en la Saga del Infinito (fases 1 a 3) y la Saga del Multiverso (fases 4 a 6).
Qué es Marvel | Una editorial de cómics de Estados Unidos, fundada en 1939, creadora de Spider-Man, los Vengadores y los X-Men. Su estudio de cine, Marvel Studios, pertenece a Disney.
Cuántas películas tiene el universo Marvel | Hasta octubre de 2026 se han estrenado treinta y ocho películas de Marvel Studios, de Iron Man (2008) a Spider-Man: Brand New Day (2026). La siguiente es Avengers: Doomsday, en diciembre de 2026.
Cuál es la primera película del universo Marvel | Iron Man, de 2008, dirigida por Jon Favreau.
Quién creó a los Vengadores en los cómics | Stan Lee y Jack Kirby, en 1963.
Quién es Stan Lee | El guionista y editor que creó, con dibujantes como Jack Kirby y Steve Ditko, a Spider-Man, los Vengadores, los X-Men y los Cuatro Fantásticos. Aparecía un momento en casi todas las películas; murió en 2018.
En qué orden se ven las películas de Marvel | Por orden de estreno, empezando por Iron Man (2008), o por orden de la historia, empezando por Capitán América: El primer vengador, que ocurre en los años cuarenta.
Qué son las fases de Marvel | Los capítulos en que se agrupan las películas y series. Las fases 1, 2 y 3 forman la Saga del Infinito, que termina en Vengadores: Endgame; las fases 4, 5 y 6 forman la Saga del Multiverso.
Qué significa MCU | Son las siglas en inglés de Marvel Cinematic Universe: el Universo Cinematográfico de Marvel.
En qué año empezó el universo Marvel | En 2008, con el estreno de Iron Man.
Qué es Marvel Studios | El estudio de cine y televisión de Marvel, que produce todas las películas y series del universo. Pertenece a Disney y lo dirige Kevin Feige.
Quién es Kevin Feige | El presidente de Marvel Studios y productor de todas las películas del universo desde Iron Man. Es quien decide el rumbo de la historia.
De quién es Marvel | De The Walt Disney Company, que compró Marvel en 2009.
Cuál es la diferencia entre Marvel y DC | Son dos editoriales distintas, con universos que no se mezclan. De Marvel son Spider-Man, los Vengadores y los X-Men; de DC, Superman, Batman y Wonder Woman.
Cuántas Gemas del Infinito hay | Seis: Espacio, Mente, Realidad, Poder, Tiempo y Alma.
Quiénes son los Vengadores originales | Iron Man, Capitán América, Thor, Hulk, Viuda Negra y Ojo de Halcón: los seis que pelean juntos en la batalla de Nueva York.
Quién reunió a los Vengadores | Nick Fury, director de S.H.I.E.L.D., con su Iniciativa Vengadores.
Quién es el villano principal de la Saga del Infinito | Thanos, el titán que reúne las seis Gemas del Infinito para borrar a la mitad de los seres vivos.
Quién es el villano principal de la Saga del Multiverso | Empezó siendo Kang el Conquistador. Para las películas que cierran la saga, el gran villano anunciado es el Doctor Doom.
Cuál es la película más taquillera de Marvel | Vengadores: Endgame, de 2019, con cerca de 2.800 millones de dólares en todo el mundo.
Cuál es la película más larga de Marvel | Vengadores: Endgame, con 181 minutos.
Cuál es la próxima película de Marvel | Avengers: Doomsday, prevista para diciembre de 2026.
Cuál es la primera serie de Marvel Studios | WandaVision, de 2021: la primera serie de Marvel Studios para Disney+.
Qué son las escenas poscréditos | Escenas cortas que salen durante o después de los créditos y adelantan la siguiente historia. La primera fue la de Nick Fury al final de Iron Man.
Qué es el multiverso | El conjunto de universos paralelos al principal, cada uno con su propia versión de los personajes. Es el centro de la Saga del Multiverso.
Qué es el Blip | Los cinco años en que faltó la mitad de los seres vivos, desde el chasquido de Thanos hasta que los Vengadores los trajeron de vuelta.
Quién es el vengador más fuerte | No hay una respuesta oficial. Los candidatos de siempre son Thor, Hulk, la Capitana Marvel y la Bruja Escarlata. En Thor Ragnarok, la nave de Tony Stark reconoce a Hulk como «el vengador más fuerte».
Quién es el más inteligente de Marvel | No hay una respuesta oficial. Se suele citar a Tony Stark, Bruce Banner y Shuri; los directores de Vengadores: Infinity War dijeron que la más inteligente es Shuri.
Quién puede levantar el Mjolnir | Quien sea digno. Además de Thor, lo levantan Visión en La era de Ultrón, el Capitán América en Endgame y Jane Foster en Thor: Amor y trueno.
Quién muere en Vengadores Endgame | Natasha Romanoff, que se sacrifica en Vormir por la Gema del Alma, y Tony Stark, que muere al usar las gemas para vencer a Thanos.
Cómo murió Tony Stark | Usó las seis Gemas del Infinito para hacer desaparecer a Thanos y a su ejército. La energía de las gemas fue más de lo que su cuerpo podía resistir, y murió poco después, acompañado por Pepper, Rhodes y Peter Parker.
Cómo muere Tony Stark | Usa las seis Gemas del Infinito para hacer desaparecer a Thanos y a su ejército. La energía de las gemas es más de lo que su cuerpo puede resistir, y muere poco después, acompañado por Pepper, Rhodes y Peter Parker.
Cómo murió Iron Man | Usó las seis Gemas del Infinito para hacer desaparecer a Thanos y a su ejército. La energía de las gemas fue más de lo que su cuerpo podía resistir, y murió poco después, acompañado por Pepper, Rhodes y Peter Parker.
Cómo muere Iron Man | Usa las seis Gemas del Infinito para hacer desaparecer a Thanos y a su ejército. La energía de las gemas es más de lo que su cuerpo puede resistir, y muere poco después, acompañado por Pepper, Rhodes y Peter Parker.
Cómo murió la Viuda Negra | Se sacrificó en Vormir, lanzándose al vacío para que Clint Barton pudiera obtener la Gema del Alma.
Quién interpreta a Iron Man | Robert Downey Jr.
Quién interpreta al Capitán América | Chris Evans interpreta a Steve Rogers. Desde 2024 el Capitán América es Sam Wilson, interpretado por Anthony Mackie.
Quién interpreta a Thor | Chris Hemsworth.
Quién interpreta a Hulk | Mark Ruffalo. En la película de 2008, El increíble Hulk, lo interpretó Edward Norton.
Quién interpreta a la Viuda Negra | Scarlett Johansson.
Quién interpreta a Spider-Man | Tom Holland.
Quién interpreta a Thanos | Josh Brolin.
Quién interpreta a Loki | Tom Hiddleston.
Quién interpreta a Doctor Strange | Benedict Cumberbatch.
Quién interpreta a Pantera Negra | Chadwick Boseman interpretó a T'Challa. Tras su muerte, Letitia Wright, que es Shuri, lleva el traje.
Quién interpreta a la Bruja Escarlata | Elizabeth Olsen.
Quién le pone la voz a JARVIS | Paul Bettany, que después interpreta a Visión.
"""


def crear(destino):
    destino = Path(destino)
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)
    total = 0
    for linea in GENERALES.strip().splitlines():
        pregunta, respuesta = (p.strip() for p in linea.split(" | "))
        (destino / f"¿{pregunta}.md").write_text(f"---\ntipo: dato\n---\n{respuesta}\n", encoding="utf-8")
        total += 1
    # Cada héroe tiene dos nombres (Iron Man y Tony Stark): el parentesco se escribe con los dos, para
    # que «¿quién es la esposa de Iron Man?» se conteste igual de rápido que con «Tony Stark».
    otro_nombre = {}
    for linea in NOMBRES.strip().splitlines():
        heroe, nombre = (p.strip() for p in linea.split(" | "))
        real = re.split(r"[.,;]", nombre)[0].strip()
        if real and real != heroe:
            otro_nombre[heroe], otro_nombre[real] = real, heroe
    for linea in PARENTESCOS.strip().splitlines():
        de_quien, respuesta = (p.strip() for p in linea.split(" | "))
        quien = "Quiénes son" if de_quien.startswith(("los ", "las ")) else "Quién es"
        variantes = [de_quien]
        for nombre, otro in otro_nombre.items():
            if re.search(rf" (de|del|de la) {re.escape(nombre)}$", de_quien):
                variantes.append(re.sub(rf" (de|del|de la) {re.escape(nombre)}$", f" de {otro}", de_quien))
        for variante in variantes:
            archivo = destino / f"¿{quien} {variante}.md"
            if not archivo.exists():
                archivo.write_text(f"---\ntipo: dato\n---\n{respuesta}\n", encoding="utf-8")
                total += 1
    for linea in NOMBRES.strip().splitlines():
        heroe, nombre = (p.strip() for p in linea.split(" | "))
        (destino / f"¿Cuál es el nombre real de {heroe}.md").write_text(
            f"---\ntipo: dato\n---\n{nombre}.\n", encoding="utf-8")
        total += 1
    return total


if __name__ == "__main__":
    print(f"{crear(sys.argv[1])} datos rápidos")
