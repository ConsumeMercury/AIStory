"""
District story pipeline catalog — many unique questlines per city district.

Each entry: title, theme (for NPC behaviour), hooks (opening angles), stages (5-beat arc).
One pipeline is chosen at world generation per district without an institution plot.
"""

DISTRICT_STORYLINE_POOLS = {
    "market": [
        {
            "title": "The Price of Everything",
            "theme": "corruption",
            "hooks": [
                "Merchants whisper that someone is fixing weights at the public scales — and the clerk who complained has stopped coming to work.",
                "A stall burns each night at the same hour; the watch says accident, but the ash smells of lamp oil.",
                "Coin from the eastern caravans arrives light; someone is shaving silver before the guild counts it.",
            ],
            "stages": [
                "rumours of cheating spread through the stalls like grease smoke",
                "a respected merchant accuses a rival at the guild steps",
                "guards take an interest in the scales — then look away too quickly",
                "ledgers and witnesses contradict each other under pressure",
                "the truth costs someone their licence, their life, or the market's last honest scale",
            ],
        },
        {
            "title": "The Silent Auction",
            "theme": "intrigue",
            "hooks": [
                "Bids appear in chalk on a back wall — goods change hands after curfew with no daylight receipt.",
                "A spice merchant vanished the night after winning a lot no rival could afford.",
                "Warehouse keys circulate among stall-holders who swear under oath they never met.",
            ],
            "stages": [
                "whispers of a buyers' circle that meets when the bell stops ringing",
                "a runner is caught with a sealed lot list and no tongue left to name names",
                "violence at the loading yard over a lot sold twice",
                "the auctioneer is traced to a noble purse or a thieves' vault",
                "the circle closes ranks — or the market burns with its secrets",
            ],
        },
        {
            "title": "Rotten Ledger",
            "theme": "corruption",
            "hooks": [
                "Fresh fruit rots overnight in stalls that paid protection — untouched stalls stay sweet.",
                "A scribe offers to reconcile debts for a fee paid in secrets, not coin.",
                "Two guild seals appear on the same contract; both masters call the other a forger.",
            ],
            "stages": [
                "merchants compare ruined stock and find the same chalk mark on each door",
                "a debt-collector is found beaten behind the grain shed, his book empty",
                "forged receipts implicate a trader too respected to accuse aloud",
                "the scribe's clients start disappearing before their appointments",
                "the ledger opens — or someone silences every hand that can read it",
            ],
        },
        {
            "title": "Honey Cartel",
            "theme": "crime",
            "hooks": [
                "Sweet stalls do brisk trade while customers stagger away pale and sweating.",
                "A child dies after eating honey cakes; the baker swears his recipe hasn't changed in twenty years.",
                "Apothecaries pay double for beeswax — and ask no questions about the colour.",
            ],
            "stages": [
                "more stalls adopt the same honey supplier overnight",
                "a healer names poison masked in sugar; the supplier vanishes",
                "street hawkers sell antidote at prices that only make sense if they knew first",
                "the cartel tries to buy the healer's silence with coin and threats",
                "the hive is burned — or becomes the only pharmacy left standing",
            ],
        },
        {
            "title": "The Weighmaster's Debt",
            "theme": "corruption",
            "hooks": [
                "The weighmaster's thumb stays on the scale for certain faces and certain hours.",
                "His daughter wears silk in a district where he claims to earn clerk's wages.",
                "Caravan masters pay a 'tolerance fee' in cash that never appears in guild books.",
            ],
            "stages": [
                "apprentices compare notes and find the same names always win on weight",
                "a caravan refuses to pay; goods sit rotting while lawyers argue",
                "the weighmaster's house is searched — and someone warned him first",
                "guild masters argue whether to protect him or sacrifice him",
                "justice, cover-up, or a new weighmaster who learns the old tricks",
            ],
        },
        {
            "title": "Silk Without Labels",
            "theme": "intrigue",
            "hooks": [
                "Unmarked bales of eastern silk appear in a locked warehouse no one admits to renting.",
                "A tailor's shop sells patterns that match stolen court gowns stitch for stitch.",
                "Customs insists nothing illegal crossed the gate — but the looms never stopped.",
            ],
            "stages": [
                "merchants undercut each other selling identical rare cloth",
                "a raid finds labels cut off and re-sewn in the back room",
                "a noble accuses the market of dressing assassins in house colours",
                "the warehouse lease leads to a name too high to touch — or too dead to matter",
                "the silk burns, the nobles pay, or the market learns to fence for lords",
            ],
        },
        {
            "title": "Bell of Closing",
            "theme": "crime",
            "hooks": [
                "After the closing bell, stall shutters lock from outside — traders still inside pound until morning.",
                "Someone collects 'night fees' to let merchants leave before dawn.",
                "Three traders who refused to pay were found in the canal with their scales in their pockets.",
            ],
            "stages": [
                "stall-holders share stories of nights spent locked in with their own stock",
                "a guard patrol changes route the week the bell ringer falls ill",
                "a merchant sets a trap and catches a familiar face with the padlock key",
                "the extortion ring offers the market protection from itself",
                "the bell ringers change, the fees end, or the market learns to sleep in shifts",
            ],
        },
    ],
    "docks": [
        {
            "title": "Harbour Secrets",
            "theme": "smuggling",
            "hooks": [
                "Crates marked for the temple never reach the road — the tally clerk has a new limp.",
                "Sailors refuse the night shift on Pier Three; they won't say why, only that the water listens.",
                "A body was found in the water at dawn — by noon the watch insists the tide took nothing.",
            ],
            "stages": [
                "cargo goes missing between ship and shed with no broken seal",
                "a customs clerk asks one question too many and stops coming to work",
                "knife-work after dark on the quay; witnesses look at their shoes",
                "the smuggling ring names its price — coin, silence, or blood",
                "the harbour master chooses a side, or the water takes another nameless debtor",
            ],
        },
        {
            "title": "The Drowned Manifest",
            "theme": "intrigue",
            "hooks": [
                "A ship arrives with fewer hands than its papers claim — the captain smiles and shows different ink.",
                "Fishers pull up nets full of sealed letters, wax unbroken, addresses still legible.",
                "The tide leaves brass tags on the mud — each stamped with a noble house that denies sending cargo.",
            ],
            "stages": [
                "clerks argue over manifests that don't match the hull or the crew's eyes",
                "a sailor jumps rather than answer who paid for the voyage",
                "letters name people still alive — and debts owed by people already buried",
                "noble messengers arrive to collect what the sea returned",
                "the harbour master burns the manifest, sells it, or disappears with the tide",
            ],
        },
        {
            "title": "Night Pier",
            "theme": "smuggling",
            "hooks": [
                "Lanterns on Pier Three go out at the same minute every night — on schedule, like a signal.",
                "Dockhands speak of singing from empty holds; the songs match no language they know.",
                "A crate of weapons was unloaded with no order filed — the shed lock was never broken.",
            ],
            "stages": [
                "night crews swap shifts without ever meeting the day crew face to face",
                "a guard post is found empty, meal still warm, boots still by the chair",
                "weapons change hands in the fog between sheds; no names, only numbers",
                "someone runs the pier like a private kingdom — and recruits openly",
                "the night pier goes dark forever, or names its price for the whole harbour",
            ],
        },
        {
            "title": "Press Gang",
            "theme": "crime",
            "hooks": [
                "Sailors wake in foreign bunks with no memory of signing papers.",
                "Tavern keepers near the quay pay protection to men who aren't the watch.",
                "A mother's son was taken from the alehouse; the captain's ledger lists him as volunteer.",
            ],
            "stages": [
                "families compare notes and find the same faces outside every disappearance",
                "a press-gang is interrupted mid-snatch; one captor drops a garrison token",
                "ships leave short-handed anyway — someone forges the crew lists",
                "the gang's patron is named in whispers too loud to unsay",
                "the gangs scatter, the navy gets its men, or the docks learn to fight back",
            ],
        },
        {
            "title": "Salt Curse",
            "theme": "intrigue",
            "hooks": [
                "Sailors from one hold fall ill with the same fever — the cargo manifest lists only salt.",
                "The ship's priest refuses to bless the unload; he crosses himself when the crates move.",
                "Fish taken near the infected berth taste of copper and rot within the hour.",
            ],
            "stages": [
                "healers argue plague against poison against something older",
                "a crate breaks open in the rain — what's inside isn't salt",
                "the captain sells cheap salt while richer buyers pay to keep mouths shut",
                "the quarantine rope goes up; smugglers slip through anyway",
                "the truth is buried at sea, sold to alchemists, or starts a panic that empties the harbour",
            ],
        },
        {
            "title": "The Empty Lighthouse",
            "theme": "smuggling",
            "hooks": [
                "The harbour light burns green on nights when ships run without lanterns.",
                "The keeper hasn't been seen in a week; his log lists perfect weather every day.",
                "Wreckers' loot washes up on Pier One — always after the light changes colour.",
            ],
            "stages": [
                "pilots whisper that the light guides more than honest hulls",
                "a ship grounds on a charted shoal the keeper swore was deep water",
                "investigators find a second lamp hidden in the keeper's cellar",
                "merchants who paid for wrecks name each other in a chain of blackmail",
                "the light is relit honestly, sold to smugglers, or smashed for good",
            ],
        },
        {
            "title": "Bride of the Tide",
            "theme": "intrigue",
            "hooks": [
                "A ship flies wedding colours but carries no bride — only locked cabin and armed escort.",
                "Dockside fortune-tellers refuse readings for sailors on that berth.",
                "Coins stamped with a drowned queen's profile circulate only among night loaders.",
            ],
            "stages": [
                "rumours tie the ship to a marriage pact between houses that hate each other",
                "a stowaway jumps overboard rather than be returned to the cabin",
                "the 'bride's' dowry is opened — papers, not jewels",
                "assassins and diplomats arrive on the same tide",
                "the marriage lands, the ship scuttles, or the harbour inherits a war",
            ],
        },
    ],
    "temple_row": [
        {
            "title": "Faith and Debt",
            "theme": "heresy",
            "hooks": [
                "Penitents queue longer each dawn; clerics look afraid of their own congregation.",
                "A relic promised to the altar has not arrived — the courier's horse did, riderless.",
                "Someone preaches in the alleys words the temple forbids; crowds grow while guards hesitate.",
            ],
            "stages": [
                "whispers of heresy among acolytes who stop meeting each other's eyes",
                "a cleric disappears after evening rites; their sandals remain by the door",
                "the high priest calls a closed judgement — servants are turned away",
                "faithful and faithful split over one sentence in an old text",
                "blood is washed from the steps — or the temple splits into two doors",
            ],
        },
        {
            "title": "The Lenten Coin",
            "theme": "corruption",
            "hooks": [
                "Offering bowls weigh light though the crowds grow heavier each week.",
                "A penitent claims the saints spoke in the crypt; the temple denies she was ever admitted.",
                "Chalk symbols appear on chapel doors each morning, scrubbed by noon without fail.",
            ],
            "stages": [
                "acolytes whisper tithes vanish before they reach the vault",
                "a lay-brother is caught copying ledgers by moonlight with the wrong hand",
                "the forbidden preacher draws a crowd the guards are ordered not to touch",
                "the high priest's judgement names a thief, a saint, or himself",
                "faith is restored at a cost — or the lenten coin buys a private army",
            ],
        },
        {
            "title": "Relics for Sale",
            "theme": "heresy",
            "hooks": [
                "Pilgrims pay to touch a bone that may not be holy; miracles happen too often to dismiss.",
                "A merchant's daughter was cured — then cursed — after a blessing that wasn't on the calendar.",
                "The reliquary room is locked; even acolytes aren't admitted without the high priest's ring.",
            ],
            "stages": [
                "rumours of false relics sold to fund a militia no sermon mentioned",
                "a cleric breaks seal to compare two bones that shouldn't both exist",
                "the merchant demands restitution in public; the crowd chooses sides",
                "a second reliquary appears in the market — identical, cheaper",
                "faith is restored, the fraud burns, or the temple sells its last honest name",
            ],
        },
        {
            "title": "The Penitent Engine",
            "theme": "intrigue",
            "hooks": [
                "A mechanical confessional clicks behind the chapel — penitents enter, few speak of what they heard.",
                "Engineers from the market tune brass gears while clerics argue doctrine at the door.",
                "Secrets told to the engine reach merchants before the penitent leaves the row.",
            ],
            "stages": [
                "confessors notice their penitents' sins repeated back as gossip in the square",
                "a acolyte finds recording wax hidden in the confession grille",
                "the engineer demands payment from both temple and guild",
                "the faithful riot over machine versus miracle",
                "the engine is destroyed, sanctified, or sold to the highest blackmailer",
            ],
        },
        {
            "title": "Saints of the Ratlines",
            "theme": "crime",
            "hooks": [
                "Street shrines appear overnight in the warrens — the temple didn't consecrate them.",
                "Offerings left at gutter altars vanish before dawn collectors arrive.",
                "A cleric is seen blessing knives in a basement the temple disowns.",
            ],
            "stages": [
                "two faiths compete for the same poor parish without sharing bread",
                "a miracle in the ratlines embarrasses the high altar",
                "the temple sends inquisitors; the streets send warnings first",
                "a saint's name becomes a gang sign or a hymn",
                "the ratline saints are absorbed, outlawed, or become the new orthodoxy",
            ],
        },
        {
            "title": "The Liturgical War",
            "theme": "heresy",
            "hooks": [
                "Two choirs sing different versions of the same hymn; both claim the oldest manuscript.",
                "Acolytes from rival chapels brawl with incense burners instead of fists.",
                "Pilgrims must choose a door; choosing wrong means refused burial rites.",
            ],
            "stages": [
                "scholars date the texts — both are older than the city walls",
                "a fire in the scriptorium destroys one copy — too conveniently timed",
                "nobles pick sects like colours for the season",
                "the high priest tries to merge rites; both sides call it betrayal",
                "one faith wins, both share the row uneasily, or blood mixes with holy water",
            ],
        },
        {
            "title": "Miracles for Hire",
            "theme": "corruption",
            "hooks": [
                "Healing miracles cluster around one cleric — always after a donation threshold is met.",
                "A cripple walks on festival day; by morning he cannot stand and won't speak.",
                "Merchants sponsor 'saint days' that coincide with their competitor's misfortune.",
            ],
            "stages": [
                "witnesses compare notes and find the same herbs under the altar cloth",
                "a rival cleric exposes a trick and is accused of envy",
                "the crowd demands a miracle on the spot — no preparation time",
                "patrons scramble to fund or debunk the next spectacle",
                "miracles end, go underground, or become the temple's official revenue",
            ],
        },
    ],
    "the_warrens": [
        {
            "title": "What the Law Doesn't See",
            "theme": "crime",
            "hooks": [
                "Children carry messages for coin; adults pretend not to notice until their own door is marked.",
                "A landlord's collector was beaten in the stairwell — his book was taken, not his purse.",
                "Forged travel papers sell from a basement room; the real clerk was found drunk, not dead.",
            ],
            "stages": [
                "rent rises and doors are marked in chalk overnight",
                "a gang claims the lower alleys and taxes bread",
                "an informant turns up drowned in a cistern everyone shares",
                "families choose between paying, fleeing, or fighting",
                "the warrens choose a boss — or burn for refusing one",
            ],
        },
        {
            "title": "Chalk Marks",
            "theme": "crime",
            "hooks": [
                "Doors marked in chalk are left alone by collectors — until yours is marked wrong.",
                "A midwife knows which families owe more than coin; she stops delivering to unmarked houses.",
                "Basement fights draw bets from guards who should stop them and don't.",
            ],
            "stages": [
                "families compare marks and find one hand wrote them all",
                "a collector is caught with his own chalk and someone else's debt list",
                "the boss behind the marks sends invitations, not threats",
                "a marked door burns; the whole stairwell chooses sides",
                "the warrens pay the debt in blood, coin, or a new ruler with clean chalk",
            ],
        },
        {
            "title": "The Paper Seller",
            "theme": "intrigue",
            "hooks": [
                "Travel papers appear overnight — good enough to pass a lazy gate, wrong enough to hang you at a strict one.",
                "Someone hunts forgers; the wrong doors get kicked in while the seller moves house.",
                "A child carries a stack of seals that shouldn't exist; she thinks they're playing cards.",
            ],
            "stages": [
                "forged papers implicate a family trying to flee before the rent comes due",
                "the seller raises prices as the garrison tightens checks at the gate",
                "a real clerk is found dead with blank forms stolen from the high quarter",
                "refugees, criminals, and nobles all need the same forger",
                "the network is exposed, buys the gate, or vanishes into a new basement",
            ],
        },
        {
            "title": "The Rat King",
            "theme": "crime",
            "hooks": [
                "Rats avoid one cellar as if trained; men don't.",
                "Someone claims title to the lower tunnels and collects tolls in teeth and coin.",
                "Traps set for vermin snap on human fingers; nobody reports it to the watch.",
            ],
            "stages": [
                "tunnel maps circulate drawn in grease on bread wrappers",
                "a merchant's shipment is diverted through the ratlines untouched by customs",
                "the Rat King's envoys speak politely and carry very clean knives",
                "the watch offers reward; the warrens offer silence",
                "a king is crowned in the dark, drowned in sewage, or bought off with a charter",
            ],
        },
        {
            "title": "Tenement Fever",
            "theme": "intrigue",
            "hooks": [
                "Coughing spreads floor by floor; landlords still collect full rent.",
                "A healer who asked for clean water was evicted; her patients weren't.",
                "Bodies are removed at night; the morning census shows no deaths.",
            ],
            "stages": [
                "neighbours share herbs and blame in equal measure",
                "a clerk from the high quarter tours the warrens with vinegar and no help",
                "someone profits selling false cures and real poison",
                "the healthy are quarantined with the sick to hide the numbers",
                "the fever breaks, the landlords hang, or the warrens empty overnight",
            ],
        },
        {
            "title": "Blood Sport Ledger",
            "theme": "crime",
            "hooks": [
                "Basement pits fill on fight nights; winners owe more than losers.",
                "A champion dies; his debt passes to his sister by rules nobody wrote down.",
                "Guards collect bribes to arrive late; surgeons arrive early.",
            ],
            "stages": [
                "bettors include names you'd recognise from the market square",
                "a fixed fight goes wrong when the loser refuses to fall",
                "the ledger lists patrons too high for the watch — and too low for honour",
                "a debtor tries to buy freedom with someone else's life",
                "the pits close, move deeper, or crown a champion who owns the warrens",
            ],
        },
        {
            "title": "The Whisper Broker",
            "theme": "intrigue",
            "hooks": [
                "Secrets sell for copper in a café with no sign; everyone knows the table.",
                "A whisper about you reaches your enemy before you speak it aloud.",
                "The broker pays children to repeat what they hear at home — and pays parents to forget.",
            ],
            "stages": [
                "nobles and thieves use the same broker with different passwords",
                "a false rumour starts a real knife fight between gangs",
                "someone tries to kill the broker; the queue for appointments grows",
                "the broker's ledger is stolen — blackmail becomes a public auction",
                "the broker flees rich, dies loud, or becomes the warrens' unofficial mayor",
            ],
        },
    ],
    "high_quarter": [
        {
            "title": "Blood and Pedigree",
            "theme": "nobility",
            "hooks": [
                "A young noble's duel was hushed up — the other boy is still missing, not dead.",
                "Servants speak of students who don't return from study hours at the academy wing.",
                "Guards were doubled at the gates without explanation; invitations still go out.",
            ],
            "stages": [
                "invitations circulate to a private gathering with no host named",
                "a scandal reaches the wrong ears at a public concert",
                "a servant is found with stolen letters and a bruise shaped like a signet ring",
                "houses trade accusations like trading cards",
                "a house falls — or buys silence at a terrible price",
            ],
        },
        {
            "title": "The Winter Salon",
            "theme": "nobility",
            "hooks": [
                "Invitations require a password no servant will repeat twice — or at all.",
                "A poet was commissioned to praise a house, then silenced with a pension instead of payment.",
                "Carriages arrive empty at midnight and leave heavy without opening the doors.",
            ],
            "stages": [
                "whispers of debts settled in the salon, not the courts",
                "a guest leaves the gathering and doesn't reach home; their shoes do",
                "letters blackmail three houses at once with the same handwriting",
                "the salon host names the next entertainment — a trial without judges",
                "the salon hosts its last party as triumph, funeral, or both",
            ],
        },
        {
            "title": "Heirless House",
            "theme": "intrigue",
            "hooks": [
                "An old name has no legitimate heir — three claimants, none liked by the servants.",
                "Servants swap allegiance weekly; the silver goes missing in turns, never all at once.",
                "The family crypt was opened from inside; dust on the outside was undisturbed.",
            ],
            "stages": [
                "genealogists are bribed to contradict each other on the same parchment",
                "a bastard child is hidden in the service wing and taught to read contracts",
                "the will is read aloud — and challenged with a blade before the ink dries",
                "claimants trade murders polite enough for the salon",
                "one claimant wins, or the house dies with its secrets in the crypt",
            ],
        },
        {
            "title": "The Garden Duel",
            "theme": "nobility",
            "hooks": [
                "Duels move from the field to the hedge maze — witnesses 'lose' their way out.",
                "A surgeon keeps hours matching the garden gate, not the hospital.",
                "Love letters and challenge notices share the same wax colour this season.",
            ],
            "stages": [
                "rumours tie the maze to affairs the church would notice",
                "a body is found in the fountain dressed for a party, not a fight",
                "servants are paid to forget paths they sweep daily",
                "the host cancels all events except one private moonlit walk",
                "honour is satisfied, buried in the roses, or exposed in court",
            ],
        },
        {
            "title": "Borrowed Titles",
            "theme": "intrigue",
            "hooks": [
                "A stranger wears a house colour at the gate; the real heir is still abroad.",
                "Tailors rush orders for crests that belong to families currently in mourning.",
                "Ball invitations arrive for people who died last winter — and someone accepts.",
            ],
            "stages": [
                "servants compare the stranger's habits to the child they raised",
                "a genealogist recants a certification for coin and fear",
                "the impostor is better liked than the legitimate heir",
                "assassins arrive for the wrong brother",
                "titles revert, double, or pass to the best liar",
            ],
        },
        {
            "title": "The Ambassador's Daughter",
            "theme": "intrigue",
            "hooks": [
                "A foreign envoy's daughter vanishes from a guarded terrace; the envoy smiles in public.",
                "Suitor gifts pile up while she is 'resting'; her maid sells answers by the hour.",
                "Treaty papers wait unsigned; ransom notes use diplomatic cipher.",
            ],
            "stages": [
                "city factions argue whether to help or exploit the disappearance",
                "a suitor is found paying guards to look away, not to kidnap",
                "the daughter sends a message — or someone forges her hand well",
                "rescue becomes scandal when she's found somewhere she chose to be",
                "war, wedding, or quiet exile closes the affair",
            ],
        },
        {
            "title": "Crypt Purchases",
            "theme": "corruption",
            "hooks": [
                "Burial plots in the high crypt sell to merchants whose names aren't noble yet.",
                "Old bones are relocated to make room; families claim the wrong skulls.",
                "A stonemason finds hollow statues with ledgers inside.",
            ],
            "stages": [
                "priests argue whether coin can buy eternity",
                "a merchant's funeral draws more guards than mourners",
                "relocated bones include evidence of poison decades old",
                "nobles buy silence with crypt keys instead of gold",
                "the dead keep their secrets, or the crypt opens to the market",
            ],
        },
    ],
}
