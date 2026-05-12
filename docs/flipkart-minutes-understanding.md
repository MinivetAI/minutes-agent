# Flipkart Minutes: Working Understanding

This document captures the current working understanding of Flipkart Minutes based on:

- the actual Minutes catalog extract in `/home/aditya/Minivet/minutes/data/minutes_catalog.tsv`
- comparison with the existing `shopsy-agent` and `food-agent`
- a product-level reading of Indian quick-commerce behavior

This is not yet an architecture document. Its purpose is to define the product reality that architecture must serve.

## 1. Core Thesis

Flipkart Minutes should be understood as an `immediate-life-commerce` system.

It is not just:

- grocery delivery
- small-format e-commerce
- a western-style quick-commerce convenience layer

It is a broader Indian instant retail system for resolving real-life needs quickly.

The catalog itself makes this clear. It includes:

- grocery and staples
- dairy, beverages, snacks, confectionery
- OTC and prescription medicine
- grooming and personal hygiene
- household supplies and cleaning
- spiritual and festive products
- flowers and party supplies
- mobiles, headphones, wearables, accessories
- shirts, jeans, bras, innerwear, ethnic sets, kids clothing

So the central product question is not:

`What is the category?`

It is:

`What real-life situation becomes worth solving immediately in modern India?`

That is the correct lens for Minutes.

## 2. What the Catalog Tells Us

The catalog size is about 77k products. It is broad, but not infinite. It is much smaller than full marketplace commerce and far more stable than a food-delivery menu universe.

A quick scan of the catalog shows strong representation from:

- `FoodAndNutrition`
- `HealthCare`
- `Grooming`
- `HouseHold`
- `Mobile`
- `Audio`
- `LifeStyle`
- `HomeDecor`

The catalog also includes product families that would look surprising if viewed through a shallow grocery-first lens:

- shirts
- jeans
- bras
- innerwear
- watches
- flowers
- pooja items
- disposable cups
- phone handsets
- phone cases
- headphones

This means the catalog is not a mistake. The catalog is the product thesis.

The thesis appears to be:

`If a product can solve a same-hour household, personal, social, work, ritual, travel, grooming, or consumption need, it can belong in Minutes.`

## 3. Why This Is Different from Shopsy and Food

### Versus Shopsy

Shopsy is a broad retail taxonomy and query-routing problem.

Minutes is narrower, but more situational:

- fewer products
- more repeated needs
- more urgency
- more contextual purchasing
- more mission-driven substitution

So broad category routing is not enough.

### Versus Food

Food is locality-bounded and menu-dynamic.

Minutes is different:

- the product universe is more canonical
- the same products broadly recur across users and geographies
- the primary retrieval object is SKU / FSN
- substitutions are common and often acceptable
- user need-state may matter more than locality-specific assortment nuance

So Minutes is not just a smaller version of Food discovery either.

## 4. Right Mental Model for Minutes

The system should reason at four layers:

1. `FSN / SKU`
2. `Variant family`
3. `Canonical product concept`
4. `Intent / mission / life situation`

Examples:

- `Amul Taaza 1L` -> exact FSN / variant / milk concept / breakfast + tea + daily stockout mission
- `formal white shirt` -> apparel concept / office-readiness mission
- `sanitary pads` -> care concept / period-care mission
- `paper cups + chips + cold drink` -> social hosting mission
- `earbuds` -> replacement or commute-readiness mission
- `pooja oil` -> ritual-readiness mission

The key point is that people are not just buying products. They are restoring continuity in everyday life.

## 5. Why People Use Minutes

The current working belief is that Minutes works because it compresses recovery time for common interruptions.

Those interruptions can be:

- household stockouts
- forgotten items
- blocked meal plans
- grooming or appearance issues
- work or school readiness gaps
- child-care and baby-care needs
- small health and wellness needs
- hosting and gifting needs
- ritual and festive needs
- accessory failures and device replacement needs
- cravings and instant consumption needs

This is why “10 minutes” changes behavior. It reduces:

- planning overhead
- travel overhead
- embarrassment or inconvenience
- routine disruption
- opportunity cost

In many Indian urban contexts, the user is not asking:

`Can I get this online?`

They are asking:

`Can I get this now without breaking the rest of the day?`

## 6. Product Selection Principle

A product belongs in Minutes if it satisfies one or more of these conditions:

- high stockout probability
- high interruption cost when missing
- high routine relevance
- high immediacy value
- strong basket-completion role
- high impulse value
- strong role in work, school, travel, care, or hosting readiness
- strong role in ritual or festive readiness
- strong substitution tolerance
- low-consideration buying behavior

This is why apparently disparate products can all belong together.

The unifying principle is not category similarity. It is immediacy of need.

## 7. Intent Map

The current working intent map contains 24 top-level intents.

These are not taxonomy buckets. They are user-side reasons for using Minutes.

### 1. Pantry Stockout

The user ran out of everyday kitchen basics.

Typical missions:

- rice finished
- atta refill
- dal refill
- sugar or salt over
- cooking oil refill
- masala refill
- tea or coffee refill

### 2. Meal Completion

The user is cooking and is blocked by one or more missing ingredients.

Typical missions:

- breakfast ingredient rescue
- lunch ingredient rescue
- dinner ingredient rescue
- curry base completion
- salad completion
- sandwich completion
- dessert ingredient completion

### 3. Fresh Produce Top-Up

The user needs fruits or vegetables quickly for immediate or near-term use.

Typical missions:

- today’s sabzi
- fruit for home
- garnish and herbs
- lemon, onion, tomato rescue
- cut fruit or quick produce need

### 4. Dairy and Breakfast Rescue

The user needs breakfast-enabling products urgently.

Typical missions:

- milk for tea
- milk for children
- curd for meal
- paneer for cooking
- bread-butter-jam rescue
- cereal or oats rescue
- eggs for breakfast or baking

### 5. Snack and Craving Fulfilment

The user wants immediate indulgence or light consumption.

Typical missions:

- evening snack
- late-night craving
- sweet craving
- salty craving
- movie snack run
- work-break snack
- stress snack

### 6. Beverage and Hydration

The user needs drinks for self, family, or guests.

Typical missions:

- cold drink for now
- juice for home
- buttermilk or lassi
- energy drink
- tea and coffee restock
- hydration during heat

### 7. Ice Cream and Dessert

The user wants instant treat or dessert completion.

Typical missions:

- dessert after dinner
- guest dessert
- kids treat
- celebration sweetening
- summer cool-down

### 8. Home Cleaning Recovery

The user needs products that restore household cleanliness quickly.

Typical missions:

- dishwashing rescue
- laundry rescue
- floor cleaning refill
- bathroom cleaning refill
- fabric stain emergency
- kitchen cleaning refill

### 9. Household Consumables Refill

The user needs non-food recurring home-use essentials.

Typical missions:

- garbage bags
- tissues
- foil or storage products
- containers
- scrub pads
- matchbox or lighter

### 10. Personal Hygiene

The user needs everyday hygiene products urgently.

Typical missions:

- soap refill
- body wash refill
- toothbrush replacement
- toothpaste refill
- deodorant rescue
- intimate hygiene need

### 11. Hair, Skin, and Grooming

The user needs grooming products for appearance or routine care.

Typical missions:

- shampoo refill
- face wash refill
- moisturizer need
- shaving rescue
- hair oil refill
- grooming before outing

### 12. Period-Care and Women’s Care

The user needs immediate care products where delay is costly.

Typical missions:

- sanitary pad emergency
- pantyliner refill
- overnight protection
- travel-care refill

### 13. Baby-Care Continuity

The user is maintaining or rescuing baby routine continuity.

Typical missions:

- diaper stockout
- wipes refill
- baby soap or lotion refill
- feeding accessory need
- baby snack or support item

### 14. Basic Health and OTC Relief

The user needs immediate health-support products.

Typical missions:

- pain relief
- fever support
- acidity or digestion relief
- vitamins and supplements
- ORS and hydration support
- cough and cold support

### 15. Prescription Continuity

The user needs medicine continuity where delay is operationally painful.

Typical missions:

- regular medicine refill
- missed reorder recovery
- urgent prescription continuation
- caretaker refill for family member

### 16. Office-Readiness

The user needs to become presentable or prepared for work quickly.

Typical missions:

- formal shirt needed now
- innerwear stockout before leaving
- socks or basics replacement
- deodorant or grooming rescue
- charger or earbud replacement before commute

### 17. School and Kids-Readiness

The user needs to restore school or child routine quickly.

Typical missions:

- school snack
- school bottle or cup
- stationery rescue
- grooming or hygiene item for child
- clothing gap for child

### 18. Travel-Readiness

The user needs items before leaving home or while preparing to travel.

Typical missions:

- toiletry refill
- charger or cable replacement
- small bag or accessory
- water bottle
- medicine carry need
- grooming and appearance prep

### 19. Appearance and Outfit Recovery

The user needs to fix a clothing or appearance problem quickly.

Typical missions:

- missing bra or innerwear
- shirt for office or outing
- jeans or bottomwear replacement
- ethnic set for event
- kids outfit need
- stain or laundry failure recovery

### 20. Device Failure or Accessory Replacement

The user needs a small electronics recovery quickly.

Typical missions:

- cable broken
- charger missing
- phone cover need
- earbuds replacement
- smartwatch strap or quick wearable purchase
- low-cost handset need

### 21. Gifting and Flowers

The user needs to fulfill a social obligation or warm gesture quickly.

Typical missions:

- birthday flowers
- greeting-card add-on
- small gift rescue
- last-minute present
- visiting someone empty-handed avoidance

### 22. Hosting and Gathering

The user is preparing for guests or a casual social event.

Typical missions:

- snack spread
- soft drinks for group
- disposable cups and plates
- sweets for guests
- tea-time hosting
- game-night style impulse basket

### 23. Ritual and Festive Readiness

The user needs products for pooja, rakhi, Diwali, or other ritual moments.

Typical missions:

- pooja oil
- agarbatti or puja samagri
- rakhi and roli
- diya or lights
- deity clothing
- festive decor

### 24. Celebration and Party Prep

The user needs lightweight event products with low lead time.

Typical missions:

- balloons
- candles
- party props
- sweets and snacks
- return-gift style items
- decor and table setup

## 8. Missions That Cut Across Intents

Some missions recur across many intents and should likely become reusable semantic features:

- `rescue`
- `top-up`
- `refill`
- `hosting`
- `readiness`
- `appearance`
- `care`
- `routine continuity`
- `gift obligation`
- `ritual obligation`
- `commute readiness`
- `guest readiness`
- `late-night consumption`
- `heat / summer response`
- `child continuity`

These cross-cutting mission traits are likely more useful than taxonomy alone for retrieval and explanation.

## 9. What This Means for Retrieval

The primary retrieval object can remain `FSN`.

But semantic retrieval should reason over:

- exact product
- family / variant
- concept
- mission

This matters because the user can express intent at many levels:

- exact: `Amul Taaza 1L`
- family: `Jockey bra`
- concept: `dishwash liquid`
- mission: `something for office tomorrow morning`
- bundle-like need: `guests are coming`

The system should be able to move between these levels.

## 10. Substitution Model

Substitution is not an edge case in Minutes. It is central.

The likely fallback order is:

1. exact FSN
2. same brand, nearby variant
3. same product concept
4. mission-preserving substitute

Examples:

- exact milk brand unavailable -> nearby pack or similar milk brand
- exact shirt unavailable -> similar formal shirt matching office-readiness mission
- exact sanitary pad unavailable -> close functional substitute
- exact snack unavailable -> same craving profile substitute

The substitution engine should understand when exactness is important and when mission completion is more important.

## 11. Brand Sensitivity

Not all Minutes products behave the same way.

Some are highly brand-sensitive:

- medicine
- baby care
- hygiene
- innerwear
- phones and electronics

Some are moderately brand-sensitive:

- packaged foods
- beauty and grooming
- detergents

Some are often mission-first or concept-first:

- fresh produce
- disposables
- some hosting items
- some ritual support items

This means brand sensitivity should become an explicit semantic property, not an assumption.

## 12. Product Metadata We Will Eventually Need

For each canonical product family, the system will likely need enrichment such as:

- primary intents served
- common missions served
- urgency level
- stockout likelihood
- substitution tolerance
- brand sensitivity
- complement products
- likely household types
- daypart sensitivity
- festive or seasonal relevance
- social-use relevance
- care-use relevance
- readiness-use relevance

This is the bridge between raw catalog taxonomy and good semantic search.

## 13. Implications for Minutes-Agent

The `minutes-agent` should probably not be centered on broad category routing.

It should likely focus on:

- query understanding
- mission understanding
- exact product parsing
- unit, quantity, pack, and size extraction
- brand-sensitivity detection
- substitution generation
- complement generation
- semantic enrichment of product families
- user-memory summarization around routines and needs

This is a better fit for Minutes than a pure taxonomy-led agent.

## 14. Open Questions

The next phase should answer these:

1. Which intents dominate demand in practice?
2. Which categories are highly brand-sensitive versus mission-sensitive?
3. What is the right canonical concept layer above FSN?
4. Which missions can be inferred deterministically from taxonomy?
5. Which missions need LLM enrichment or web enrichment?
6. How should the system handle multi-item missions like hosting, office-readiness, or pooja prep?
7. What should be the semantic representation of bundles, routines, and life situations?

## 15. Next Step

The next useful artifact should be a taxonomy-grounded semantic layer for the catalog:

- map product families to intents
- map intents to missions
- identify brand-sensitive vs substitution-tolerant families
- define the enrichment schema for canonical product concepts

Once that exists, architecture will become much easier to discuss in concrete terms.
