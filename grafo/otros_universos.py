"""Crea las notas de «otros universos»: personajes y franquicias que NO son del universo Marvel.

No cuentan su historia: solo dicen quién es cada uno y de dónde viene, para que M-Jarvis no los
confunda con los héroes de Marvel y pueda aclararlo si alguien los mezcla en una pregunta.

Uso (en la Latitude): python3 otros_universos.py ~/mjarvis/conocimiento/otros-universos

Formato de DATOS:
  # Franquicia | dueño o tipo | qué es          (con ~ delante no se crea nota de la franquicia)
  Nombre = quién es, en una frase
"""
import shutil
import sys
from pathlib import Path

DATOS = """
# DC Comics | editorial de cómics rival de Marvel, de Warner Bros. | la editorial de Superman, Batman y la Liga de la Justicia
Superman = Clark Kent, o Kal-El: el último hijo del planeta Krypton, periodista en Metrópolis. Vuela, tiene superfuerza y visión de calor; su debilidad es la kryptonita
Batman = Bruce Wayne, millonario de Ciudad Gótica que combate el crimen sin superpoderes, con ingenio, entrenamiento y tecnología. También llamado el Caballero de la Noche
Mujer Maravilla = Wonder Woman, Diana de Temiscira: princesa amazona con superfuerza, brazaletes y el Lazo de la Verdad
Flash (DC) = Barry Allen, el hombre más rápido del mundo, velocista de Ciudad Central. No confundir con Flash Thompson, de Marvel
Aquaman = Arthur Curry, rey de la Atlántida, que respira bajo el agua y habla con los animales del mar. Se parece a Namor, de Marvel, pero es de DC
Linterna Verde = Green Lantern: Hal Jordan o John Stewart, policías del espacio con un anillo que crea cualquier cosa con luz verde
Cyborg = Victor Stone, joven mitad humano y mitad máquina, miembro de la Liga de la Justicia y de los Jóvenes Titanes
Shazam = Billy Batson, un niño que al decir la palabra mágica se convierte en un héroe adulto con los poderes de seis dioses
Supergirl = Kara Zor-El, la prima de Superman, con sus mismos poderes
Robin = el joven ayudante de Batman; el primero fue Dick Grayson
Nightwing = Dick Grayson, el primer Robin, ya adulto y héroe por su cuenta
Batgirl = Barbara Gordon, heroína de Ciudad Gótica, aliada de Batman
Flecha Verde = Green Arrow, Oliver Queen: arquero millonario de Star City. Se parece a Ojo de Halcón, pero es de DC
Joker = el Guasón, payaso criminal y mayor enemigo de Batman
Harley Quinn = antigua psiquiatra convertida en villana y antiheroína, compañera del Joker
Lex Luthor = genio multimillonario y calvo, el gran enemigo de Superman
Darkseid = tirano del planeta Apokolips, el villano más poderoso de DC. Se parece a Thanos, pero es anterior y es de DC
Gatúbela = Catwoman, Selina Kyle: ladrona de joyas de Ciudad Gótica, a veces aliada de Batman
El Pingüino = Oswald Cobblepot, jefe criminal de Ciudad Gótica, enemigo de Batman
El Acertijo = Riddler, villano de Batman obsesionado con los enigmas
Bane = villano enmascarado y fortísimo que le rompió la espalda a Batman
Liga de la Justicia = el gran equipo de héroes de DC: Superman, Batman, Mujer Maravilla, Flash, Aquaman, Linterna Verde y Cyborg. Es el equivalente de los Vengadores en DC
Jóvenes Titanes = Teen Titans: equipo juvenil de DC con Robin, Starfire, Raven, Chico Bestia y Cyborg, famoso por sus series animadas
Escuadrón Suicida = equipo de villanos de DC obligados a hacer misiones para el gobierno, con Harley Quinn y Deadshot
Peacemaker = el Pacificador, antihéroe de DC que busca la paz a cualquier precio
Black Adam = antihéroe de DC con los poderes de los dioses egipcios, rival de Shazam
Doomsday (DC) = el monstruo que mató a Superman en los cómics. No tiene nada que ver con la película Avengers: Doomsday
Constantine = John Constantine, detective de lo oculto y hechicero de DC
Watchmen = cómic y película de DC sobre héroes retirados, con Rorschach y el Doctor Manhattan

# Star Wars | Lucasfilm, de Disney | saga de ciencia ficción de George Lucas: «La guerra de las galaxias», con jedis, siths y la Fuerza
Luke Skywalker = granjero que se convierte en caballero jedi y derrota al Imperio
Darth Vader = Anakin Skywalker: jedi caído al lado oscuro, con armadura negra y respirador. Padre de Luke y Leia
Princesa Leia = Leia Organa, líder de la Rebelión y hermana de Luke
Han Solo = contrabandista y piloto del Halcón Milenario
Chewbacca = wookiee peludo y enorme, copiloto de Han Solo
Yoda = maestro jedi pequeño y verde, de novecientos años, que habla al revés
Obi-Wan Kenobi = maestro jedi que entrenó a Anakin y a Luke
Emperador Palpatine = Darth Sidious, señor de los sith y emperador de la galaxia
Rey (Star Wars) = chatarrera de Jakku que se convierte en jedi en la trilogía más reciente
Kylo Ren = Ben Solo, hijo de Han y Leia, caído al lado oscuro
Grogu = el pequeño de la especie de Yoda al que llaman «Baby Yoda», de la serie The Mandalorian
El Mandaloriano = Din Djarin, cazarrecompensas con armadura de beskar, protagonista de The Mandalorian
Ahsoka Tano = antigua aprendiz de Anakin Skywalker, con dos sables blancos
R2-D2 y C-3PO = los dos droides de la saga: uno pequeño que silba y otro dorado que habla seis millones de idiomas

# Harry Potter | de J. K. Rowling y Warner Bros. | saga de libros y películas sobre un niño mago y el colegio Hogwarts
Harry Potter = el niño que sobrevivió: joven mago con una cicatriz en forma de rayo, alumno de Hogwarts
Hermione Granger = la bruja más lista de su curso, amiga de Harry
Ron Weasley = el mejor amigo de Harry, de una gran familia de magos pelirrojos
Albus Dumbledore = director de Hogwarts y el mago más sabio de su tiempo
Lord Voldemort = el mago tenebroso que mató a los padres de Harry; el que no debe ser nombrado
Severus Snape = profesor de pociones, severo y de lealtad dudosa
Hagrid = guardabosques semigigante de Hogwarts
Draco Malfoy = alumno de Slytherin y rival de Harry

# El Señor de los Anillos | de J. R. R. Tolkien | saga de fantasía de la Tierra Media, con El hobbit
Frodo Bolsón = el hobbit que debe destruir el Anillo Único
Gandalf = mago gris, luego blanco, guía de la Comunidad del Anillo
Aragorn = montaraz heredero del trono de Gondor
Legolas = elfo arquero de la Comunidad del Anillo
Gollum = criatura consumida por el Anillo, al que llama «mi tesoro»
Sauron = el Señor Oscuro que forjó el Anillo Único

# Dragon Ball | anime y manga de Akira Toriyama | serie japonesa de peleas, con Dragon Ball Z y Dragon Ball Super
Goku = Son Goku, o Kakaroto: saiyajin criado en la Tierra, siempre en busca de rivales más fuertes. Se transforma en supersaiyajin y lanza el Kamehameha
Vegeta = príncipe de los saiyajin, rival orgulloso de Goku
Gohan = hijo mayor de Goku, de enorme poder oculto
Piccolo = guerrero namekiano verde, antiguo enemigo y luego maestro de Gohan
Freezer = Frieza, tirano del espacio que destruyó el planeta de los saiyajin
Bulma = inventora genial, amiga de Goku desde niño
Krilin = el mejor amigo de Goku, humano y calvo
Majin Buu = monstruo rosado y regordete, uno de los grandes enemigos de Goku
Trunks = hijo de Vegeta y Bulma; llega del futuro con una espada

# Naruto | anime y manga de Masashi Kishimoto | serie japonesa de ninjas
Naruto Uzumaki = ninja rubio de la Aldea de la Hoja que lleva dentro al zorro de nueve colas y sueña con ser Hokage
Sasuke Uchiha = rival y amigo de Naruto, último de su clan
Sakura Haruno = ninja médica, compañera de Naruto y Sasuke
Kakashi Hatake = maestro de Naruto, el ninja que copia técnicas
Itachi Uchiha = hermano mayor de Sasuke, miembro de Akatsuki

# One Piece | anime y manga de Eiichiro Oda | serie japonesa de piratas
Monkey D. Luffy = pirata de goma con sombrero de paja que quiere ser el rey de los piratas
Roronoa Zoro = espadachín de tres espadas de la tripulación de Luffy
Nami = navegante de la tripulación de Luffy
Sanji = cocinero de la tripulación de Luffy, que pelea a patadas

# Pokémon | de Nintendo y Game Freak | videojuegos, anime y cartas de criaturas coleccionables
Ash Ketchum = entrenador del anime de Pokémon, de Pueblo Paleta
Pikachu = ratón eléctrico amarillo, compañero de Ash y mascota de la franquicia
Charizard = dragón de fuego naranja, de los Pokémon más famosos
Mewtwo = Pokémon psíquico creado en un laboratorio
Equipo Rocket = Jessie, James y Meowth, los villanos torpes del anime de Pokémon

# Anime japonés | varios estudios japoneses | series japonesas de animación que no tienen relación con Marvel
Sailor Moon = Serena Tsukino, guerrera que lucha por el amor y la justicia en nombre de la Luna
Saitama (One Punch Man) = héroe calvo que vence a cualquiera de un solo puñetazo
Deku (My Hero Academia) = Izuku Midoriya, estudiante de héroe que hereda el poder de All Might
All Might = el héroe número uno de My Hero Academia, símbolo de la paz
Tanjiro Kamado = joven cazador de demonios de Demon Slayer (Kimetsu no Yaiba)
Nezuko = hermana de Tanjiro, convertida en demonio, en Demon Slayer
Eren Jaeger = protagonista de Ataque a los Titanes (Shingeki no Kyojin)
Light Yagami = estudiante que encuentra un cuaderno que mata, en Death Note; lo persigue el detective L
Gojo Satoru = el hechicero más fuerte de Jujutsu Kaisen, con los ojos vendados
Seiya de Pegaso = caballero de bronce de Los Caballeros del Zodiaco (Saint Seiya)
Doraemon = gato robot azul venido del futuro, con un bolsillo lleno de inventos
Shin-chan = niño travieso de cinco años, de un anime de comedia
Astroboy = niño robot creado por Osamu Tezuka, de los primeros animes
Totoro = espíritu del bosque grande y peludo, de la película de Studio Ghibli Mi vecino Totoro
Mazinger Z = robot gigante pilotado por Koji Kabuto, clásico de los años setenta
Sakura Kinomoto = protagonista de Sakura Card Captor, cazadora de cartas mágicas
Inuyasha = medio demonio de un anime de aventuras en el Japón feudal

# Nintendo | empresa japonesa de videojuegos | creadora de Mario, Zelda y Pokémon
Mario = fontanero bigotudo de gorra roja, héroe del Reino Champiñón y mascota de Nintendo
Luigi = hermano de Mario, alto y de verde
Princesa Peach = princesa del Reino Champiñón
Bowser = rey de los Koopas, tortuga gigante con púas, enemigo de Mario
Yoshi = dinosaurio verde amigo de Mario
Link = héroe de túnica verde de The Legend of Zelda; no se llama Zelda
Princesa Zelda = princesa de Hyrule, en The Legend of Zelda
Donkey Kong = gorila con corbata, de los primeros personajes de Nintendo
Kirby (Nintendo) = bola rosada que absorbe a sus enemigos y copia sus poderes
Samus Aran = cazarrecompensas con armadura, protagonista de Metroid

# Videojuegos | varias empresas | personajes famosos de videojuegos que no son de Marvel
Sonic = erizo azul supersónico de Sega; sus amigos son Tails y Knuckles, y su enemigo el Dr. Eggman
Steve (Minecraft) = el personaje cuadrado de Minecraft, el juego de construir con bloques; sus enemigos son los Creepers
Kratos = espartano que mata a los dioses, protagonista de God of War
Jefe Maestro = Master Chief, supersoldado con armadura verde de la saga Halo
Lara Croft = arqueóloga aventurera de Tomb Raider
Pac-Man = bola amarilla que come puntos y huye de fantasmas
Crash Bandicoot = marsupial naranja de los juegos de plataformas
Freddy Fazbear = oso animatrónico de Five Nights at Freddy's
Scorpion y Sub-Zero = ninjas rivales de Mortal Kombat, uno de fuego y otro de hielo. Ese Scorpion no es el Escorpión de Spider-Man
Ryu (Street Fighter) = luchador de karate que lanza el Hadouken
Cuphead = personaje con cabeza de taza, de un juego con estilo de dibujos antiguos
Ellie y Joel = protagonistas de The Last of Us
Geralt de Rivia = cazador de monstruos de The Witcher
Fortnite = videojuego de batalla de Epic Games; muchos héroes de Marvel aparecen en él como trajes, pero el juego no es de Marvel
Roblox = plataforma de juegos creados por sus usuarios
Among Us = juego de tripulantes e impostores en una nave

# Nickelodeon | canal de televisión infantil | canal de dibujos animados y series juveniles
Bob Esponja = esponja amarilla que vive en una piña debajo del mar y cocina en el Crustáceo Cascarudo
Patricio Estrella = estrella de mar rosada, mejor amigo de Bob Esponja
Calamardo = vecino gruñón de Bob Esponja, que toca el clarinete
Don Cangrejo = dueño tacaño del Crustáceo Cascarudo
Plankton = diminuto villano que quiere robar la fórmula de la Cangreburger
Los padrinos mágicos = serie de Timmy Turner, un niño con dos padrinos que conceden deseos, Cosmo y Wanda. Ni ese Cosmo ni esa Wanda son los de Marvel
Jimmy Neutrón = niño genio de gran peinado, inventor
Aang = el último maestro del aire, niño monje y Avatar, de Avatar: La leyenda de Aang. No tiene que ver con la película Avatar ni con Marvel
Katara y Zuko = la maestra del agua y el príncipe de la Nación del Fuego, de Avatar: La leyenda de Aang
Korra = la Avatar siguiente a Aang, de La leyenda de Korra
Dora la exploradora = niña que viaja con su mochila y su mono Botas
Tortugas Ninja = Leonardo, Raphael, Donatello y Michelangelo: cuatro tortugas mutantes adolescentes que viven en las alcantarillas, con su maestro Splinter
Danny Phantom = adolescente mitad fantasma
Rugrats = serie de bebés aventureros: Tommy, Carlitos, Angélica
Hey Arnold = niño de cabeza ovalada que vive en una pensión de la ciudad
Paw Patrol = Patrulla de cachorros: perritos rescatistas dirigidos por Ryder
Invasor Zim = extraterrestre torpe que quiere conquistar la Tierra
Los Loud = The Loud House: Lincoln Loud y sus diez hermanas
Henry Danger = serie de un chico ayudante del Capitán Man
iCarly = serie juvenil sobre un programa de internet

# Cartoon Network | canal de televisión de dibujos animados, de Warner Bros. | canal de series animadas
Ben 10 = Ben Tennyson, niño con un reloj, el Omnitrix, que lo transforma en extraterrestres
Las Chicas Superpoderosas = Bombón, Burbuja y Bellota, tres niñas con superpoderes creadas con azúcar, flores y la sustancia X; su enemigo es Mojo Jojo
El laboratorio de Dexter = serie de un niño genio con un laboratorio secreto y una hermana, Dee Dee
Johnny Bravo = joven musculoso y presumido con un gran copete
Coraje, el perro cobarde = perro rosado que protege a sus dueños de monstruos
Ed, Edd y Eddy = tres amigos que inventan estafas para comprar caramelos
Hora de Aventura = Finn el humano y Jake el perro, en la Tierra de Ooo
Un show más = Mordecai y Rigby, un arrendajo y un mapache que trabajan en un parque
El increíble mundo de Gumball = serie de un gato azul y su hermano pez, Darwin
Steven Universe = niño mitad humano, mitad gema, criado por las Gemas de Cristal. Esas gemas no son las Gemas del Infinito
Samurái Jack = samurái enviado al futuro por el demonio Aku
Los chicos del barrio = KND: niños agentes secretos contra los adultos
Las sombrías aventuras de Billy y Mandy = dos niños amigos de la Muerte, Puro Hueso
Scooby-Doo = perro gran danés miedoso que resuelve misterios con Shaggy, Fred, Daphne y Vilma
Tom y Jerry = el gato y el ratón que se persiguen sin fin
Looney Tunes = Bugs Bunny, el Pato Lucas, Porky, Piolín y Silvestre, el Coyote y el Correcaminos, y el Demonio de Tasmania
Los Picapiedra = Pedro Picapiedra y Pablo Mármol, familias de la edad de piedra
Los Supersónicos = familia del futuro con coches voladores
Rick y Morty = científico loco y su nieto, de una serie para adultos

# Disney | The Walt Disney Company, dueña también de Marvel | estudio de animación clásico; ser del mismo dueño no los hace parte del universo Marvel
Mickey Mouse = ratón de pantalones rojos, símbolo de Disney; con Minnie, Donald, Goofy y Pluto
Pato Donald = pato gruñón vestido de marinero, amigo de Mickey
Goofy = perro alto y torpe, amigo de Mickey
Simba = león protagonista de El Rey León; su tío Scar mató a su padre, Mufasa
Timón y Pumba = el suricato y el jabalí de El Rey León: hakuna matata
Stitch = experimento 626, extraterrestre azul adoptado por Lilo en Hawái
Aladdín = joven de Agrabah que encuentra una lámpara con un Genio; su enemigo es Jafar
Elsa (Frozen) = reina de Arendelle con poderes de hielo; su hermana es Anna y su amigo, el muñeco de nieve Olaf. No es Elsa Bloodstone, de Marvel
Moana = hija del jefe de una isla del Pacífico, que navega con el semidiós Maui
Mulán = joven china que se hace pasar por soldado para salvar a su padre
Rapunzel = princesa de larguísimo pelo dorado, de Enredados
Mirabel = la única de la familia Madrigal sin don mágico, de Encanto
Ariel = sirena pelirroja de La Sirenita; la bruja del mar es Úrsula
Bella = la joven lectora de La Bella y la Bestia. Esa Bestia no es el Bestia de los X-Men
Blancanieves = princesa de los siete enanitos
Cenicienta = la joven del zapato de cristal
Maléfica = el hada malvada de La Bella Durmiente
Cruella de Vil = villana que quiere un abrigo de dálmatas
Peter Pan = el niño que no quiere crecer, con el hada Campanita y el Capitán Garfio. No es Peter Parker
Pinocho = muñeco de madera al que le crece la nariz cuando miente
Winnie Pooh = oso amante de la miel, con Tigger y Piglet
Hércules (Disney) = el héroe griego de la película animada de 1997. No es el Hércules de Marvel
Tarzán = hombre criado por gorilas en la selva
Ralph el Demoledor = villano de un videojuego que quiere ser héroe
Judy Hopps = coneja policía de Zootopia, compañera del zorro Nick Wilde
Baymax = robot enfermero blanco e inflable de Grandes Héroes. La película se basa en un cómic de Marvel, pero no forma parte del universo de los Vengadores
Phineas y Ferb = dos hermanastros inventores; su mascota, Perry el ornitorrinco, es agente secreto contra el doctor Doofenshmirtz
Kim Possible = adolescente espía que salva al mundo entre clases
Gravity Falls = serie de los gemelos Dipper y Mabel y sus misterios; el villano es Bill Clave
Hannah Montana = serie de una chica que lleva una doble vida como estrella del pop
Jack Sparrow = capitán pirata de Piratas del Caribe
Rico McPato = el tío millonario de Donald, de Patoaventuras
Ladybug y Cat Noir = Marinette y Adrien, héroes de París en Miraculous

# Pixar | estudio de animación de Disney | estudio de Toy Story y otras películas animadas por ordenador
Woody = vaquero de juguete, líder de los juguetes de Andy, en Toy Story
Buzz Lightyear = guardián espacial de juguete: al infinito y más allá
Rayo McQueen = coche de carreras rojo de Cars; su amigo es la grúa Mate
Nemo = pez payaso perdido al que busca su padre, Marlin, con Dory
Mike y Sulley = Mike Wazowski y James Sullivan, los monstruos de Monsters, Inc.
Los Increíbles = familia de superhéroes de Pixar: Mr. Increíble, Elastigirl, Violeta, Dash y Jack-Jack, con su amigo Frozono. Se parecen a los Cuatro Fantásticos, pero son de Pixar
WALL-E = pequeño robot que limpia la Tierra abandonada
Remy = rata cocinera de Ratatouille
Carl y Russell = el anciano y el niño explorador de Up, la casa de los globos
Miguel (Coco) = niño músico que viaja a la Tierra de los Muertos
Alegría y Tristeza = las emociones de Intensa-Mente
Mérida = princesa arquera escocesa, de Valiente

# DreamWorks | estudio de animación | estudio de Shrek, Kung Fu Panda y Cómo entrenar a tu dragón
Shrek = ogro verde que vive en un pantano, con su amigo Burro y su esposa Fiona
Gato con Botas = gato espadachín con sombrero, amigo de Shrek
Po = panda torpe que se convierte en el Guerrero Dragón, en Kung Fu Panda
Hipo y Chimuelo = el joven vikingo y su dragón Furia Nocturna, de Cómo entrenar a tu dragón
Alex el león = león del zoológico de Nueva York, de Madagascar, con los pingüinos
Megamente = villano azul de cabeza enorme que acaba siendo héroe
Gru y los Minions = villano reformado y sus ayudantes amarillos, de Mi villano favorito, de Illumination

# Cine y televisión | varios estudios | personajes famosos de películas y series que no son de Marvel
Godzilla = monstruo gigante japonés, rey de los monstruos; pelea con King Kong
Terminator = robot asesino venido del futuro, interpretado por Arnold Schwarzenegger
Neo = el elegido de Matrix
Indiana Jones = arqueólogo aventurero con sombrero y látigo
James Bond = el agente 007 del servicio secreto británico
John Wick = asesino retirado que vuelve por venganza
Marty McFly = joven que viaja en el tiempo en un DeLorean, con el Doc Brown, en Volver al futuro
E.T. = extraterrestre perdido en la Tierra que quiere volver a casa
Los Cazafantasmas = científicos que atrapan fantasmas en Nueva York
Avatar (película de James Cameron) = película sobre el planeta Pandora y los na'vi, seres azules. No tiene relación con Marvel ni con Avatar: La leyenda de Aang
Dominic Toretto = protagonista de Rápidos y Furiosos
Katniss Everdeen = arquera protagonista de Los Juegos del Hambre
Percy Jackson = hijo de Poseidón, de una saga de libros juveniles
Sherlock Holmes = el detective más famoso de la literatura
Jurassic Park = saga de películas de un parque de dinosaurios
Optimus Prime = líder de los Autobots en Transformers; su enemigo es Megatron y su amigo, Bumblebee
Power Rangers = equipo de jóvenes con trajes de colores y robots gigantes
Once (Stranger Things) = Eleven, niña con poderes mentales de la serie Stranger Things
Jon Nieve = Jon Snow, protagonista de Juego de Tronos, con Daenerys y sus dragones
Homelander = el Patriota, el «Superman» malvado de la serie The Boys
Invencible = Mark Grayson, joven héroe hijo de Omni-Man, de la serie Invincible
Doctor Who = extraterrestre que viaja por el tiempo en una cabina azul
Spock y el capitán Kirk = tripulantes de la nave Enterprise, de Star Trek
Merlina Addams = Wednesday, la hija sombría de Los Locos Addams
Las guerreras K-pop = HUNTR/X: Rumi, Mira y Zoey, cantantes y cazadoras de demonios de la película de Netflix
He-Man = el hombre más poderoso del universo, de Masters of the Universe; su enemigo es Skeletor
Hellboy = demonio rojo con una mano de piedra, de Dark Horse Comics
Spawn = soldado vuelto del infierno, de Image Comics
Drácula y Frankenstein = monstruos clásicos de la literatura y el cine

# Dibujos y humor clásicos | varios autores | series y tiras cómicas populares
Los Simpson = familia amarilla de Springfield: Homero, Marge, Bart, Lisa y Maggie
Padre de familia = Family Guy: Peter Griffin y su familia
Futurama = serie del futuro con Fry, Leela y el robot Bender
South Park = serie para adultos de cuatro niños de Colorado
El Chavo del 8 = niño que vive en un barril en una vecindad, creado por Chespirito
El Chapulín Colorado = héroe torpe de traje rojo y antenas, de Chespirito: «no contaban con mi astucia»
Garfield = gato naranja perezoso que ama la lasaña
Snoopy = el perro de Charlie Brown, de la tira Peanuts
Mafalda = niña argentina que odia la sopa, creada por Quino
Condorito = cóndor de las historietas chilenas
Astérix y Obélix = galos que resisten a los romanos gracias a una poción mágica
Tintín = joven reportero belga, con su perro Milú
Popeye = marinero que se hace fuerte comiendo espinacas
La Pantera Rosa = pantera elegante y muda. No tiene que ver con Pantera Negra
Los Pitufos = pequeños seres azules que viven en hongos y huyen de Gargamel
Barbie = muñeca famosa, con películas propias
Hello Kitty = gatita blanca con un lazo, de Sanrio
Peppa Pig = cerdita de una serie para niños pequeños
Bluey = cachorra azul de una serie australiana
Pocoyó = niño vestido de azul de una serie española
Elmo = monstruo rojo de Plaza Sésamo
My Little Pony = ponis mágicos de colores
Max Steel = joven héroe con energía turbo, de Mattel
LEGO = juguetes de bloques; hay juegos y películas de LEGO con héroes de Marvel y de DC, pero LEGO es una marca aparte
Hotel Transylvania = películas del conde Drácula, su hija Mavis y sus amigos monstruos

# Marvel fuera del UCM | Marvel, pero con otros estudios | personajes de Marvel que no pertenecen a la historia del Universo Cinematográfico de Marvel
Miles Morales = Spider-Man de otro universo, protagonista de las películas animadas Spider-Man: Un nuevo universo, de Sony. Es de Marvel, pero aún no ha aparecido en las películas de los Vengadores
Spider-Gwen = Gwen Stacy con poderes de araña, de las películas animadas del Spider-Verso
Venom (películas de Sony) = Eddie Brock y su simbionte, con Tom Hardy. Es de Marvel, pero sus películas son de Sony y ocurren en otro universo
X-Men de Fox = las películas de los X-Men de 2000 a 2020, con Wolverine, el Profesor X y Magneto. Ocurren en otro universo, que se une al UCM en Deadpool y Wolverine y en Avengers: Doomsday
X-Men 97 = serie animada de los X-Men, continuación de la de los años noventa. Es de Marvel, pero no pertenece a la historia del UCM
Los Cuatro Fantásticos de 2005 = las películas anteriores de los Cuatro Fantásticos, con otro reparto. No son las del UCM
Ghost Rider = el Motorista Fantasma, de las películas de Nicolas Cage. Es de Marvel, pero no del UCM
Agentes de S.H.I.E.L.D. = serie de televisión de Phil Coulson y su equipo, de 2013 a 2020. Nació unida a las películas, pero hoy no se cuenta como parte de la historia principal
"""


def crear(destino):
    destino = Path(destino)
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)
    franquicia, dueno, miembros, total = None, None, [], 0

    def cerrar():
        if franquicia and not franquicia.startswith("~") and miembros:
            lista = ", ".join(f"[[{m}]]" for m in miembros)
            cierre = "" if "Marvel" in franquicia else " No forma parte del universo Marvel."
            (destino / f"{franquicia}.md").write_text(
                f"---\ntipo: otro universo\n---\n{franquicia}: {descripcion}. Origen: {dueno.rstrip(chr(46))}.{cierre} "
                f"Personajes y títulos que conozco de ahí: {lista}.\n", encoding="utf-8")

    for linea in DATOS.strip().splitlines():
        linea = linea.strip()
        if not linea:
            continue
        if linea.startswith("#"):
            cerrar()
            franquicia, dueno, descripcion = (p.strip() for p in linea[1:].split("|"))
            miembros = []
            continue
        nombre, texto = (p.strip() for p in linea.split(" = ", 1))
        origen = franquicia.lstrip("~")
        cierre = "" if "Marvel" in origen else " No pertenece al universo Marvel."
        (destino / f"{nombre}.md").write_text(
            f"---\ntipo: otro universo\n---\n{nombre}: {texto}. Viene de [[{origen}]].{cierre}\n", encoding="utf-8")
        miembros.append(nombre)
        total += 1
    cerrar()
    return total


if __name__ == "__main__":
    print(f"{crear(sys.argv[1])} notas de otros universos")
