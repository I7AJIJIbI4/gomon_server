<?php

class StoreCountry extends StoreRegion {
	/** @var string */
	public $isoCode3 = null;
	/** @var StoreRegion[] */
	public $regions = array();

	public function setISOCode3($code) {
		$this->isoCode3 = $code;
		return $this;
	}

	/**
	 * @param StoreRegion $region
	 * @return StoreCountry
	 */
	public function addRegion(StoreRegion $region) {
		$this->regions[] = $region;
		return $this;
	}
	
	/**
	 * @param string $code country code.
	 * @return StoreCountry
	 */
	public static function findByCode($code) {
		if ($code) foreach (self::buildList() as $li) {
			if ($li->code == $code) return $li;
		}
		return null;
	}

	/**
	 * @param string $isoCode3 country code.
	 * @return StoreCountry
	 */
	public static function findByIsoCode3($isoCode3) {
		if ($isoCode3) foreach (self::buildList() as $li) {
			if ($li->isoCode3 == $isoCode3) return $li;
		}
		return null;
	}


	/**
	 * @param string $countryCode country code.
	 * @param string $regionName region name.
	 * @return array
	 */
	public static function findCountryAndRegion($countryCode, $regionName) {
		$country = $region = null;
		if ($countryCode) {
			foreach (self::buildList() as $li) {
				if ($li->code == $countryCode) {
					$country = $li;
					if( $regionName ) {
						foreach( $country->regions as $r ) {
							if( $r->name == $regionName ) {
								$region = $r;
								break;
							}
						}
					}
					break;
				}
			}
		}
		return array($country, $region);
	}

	/** @return StoreCountry[] */
	public static function buildList() {
		$list = array(
			StoreCountry::create('AF', 'Афганістан')->setISOCode3('AFG'),
			StoreCountry::create('AX', 'Аландські острови')->setISOCode3('ALA'),
			StoreCountry::create('AL', 'Албанія')->setISOCode3('ALB'),
			StoreCountry::create('DZ', 'Алжир')->setISOCode3('DZA'),
			StoreCountry::create('AS', 'Американське Самоа')->setISOCode3('ASM'),
			StoreCountry::create('AD', 'Андорра')->setISOCode3('AND'),
			StoreCountry::create('AO', 'Ангола')->setISOCode3('AGO'),
			StoreCountry::create('AI', 'Ангілья')->setISOCode3('AIA'),
			StoreCountry::create('AQ', 'Антарктика')->setISOCode3('ATA'),
			StoreCountry::create('AG', 'Антигуа і Барбуда')->setISOCode3('ATG'),
			StoreCountry::create('AR', 'Аргентина')->setISOCode3('ARG'),
			StoreCountry::create('AM', 'Вірменія')->setISOCode3('ARM'),
			StoreCountry::create('AW', 'Аруба')->setISOCode3('ABW'),
			StoreCountry::create('AU', 'Австралія')->setISOCode3('AUS'),
			StoreCountry::create('AT', 'Австрія')->setISOCode3('AUT'),
			StoreCountry::create('AZ', 'Азербайджан')->setISOCode3('AZE'),
			StoreCountry::create('BS', 'Багами')->setISOCode3('BHS'),
			StoreCountry::create('BH', 'Бахрейн')->setISOCode3('BHR'),
			StoreCountry::create('BD', 'Бангладеш')->setISOCode3('BGD'),
			StoreCountry::create('BB', 'Барбадос')->setISOCode3('BRB'),
			StoreCountry::create('BY', 'Білорусь')->setISOCode3('BLR')
				->addRegion(new StoreRegion('HM', 'Місто Мінськ'))
				->addRegion(new StoreRegion('BR', 'Брестська область'))
				->addRegion(new StoreRegion('HO', 'Гомельська обл'))
				->addRegion(new StoreRegion('HR', 'Гродненська обл'))
				->addRegion(new StoreRegion('MA', 'Могильовська обл'))
				->addRegion(new StoreRegion('MI', 'Мінська обл'))
				->addRegion(new StoreRegion('VI', 'Вітебська область')),
			StoreCountry::create('BE', 'Бельгія')->setISOCode3('BEL'),
			StoreCountry::create('BZ', 'Беліз')->setISOCode3('BLZ'),
			StoreCountry::create('BJ', 'Бенін')->setISOCode3('BEN'),
			StoreCountry::create('BM', 'Бермудські острови')->setISOCode3('BMU'),
			StoreCountry::create('BT', 'Бутан')->setISOCode3('BTN'),
			StoreCountry::create('BO', 'Болівія')->setISOCode3('BOL'),
			StoreCountry::create('BA', 'Боснія і Герцоговина')->setISOCode3('BIH'),
			StoreCountry::create('BW', 'Ботсвана')->setISOCode3('BWA'),
			StoreCountry::create('BV', 'Острів Буве')->setISOCode3('BVT'),
			StoreCountry::create('BR', 'Бразилія')->setISOCode3('BRA'),
			StoreCountry::create('BQ', 'Карибські Нідерланди')->setISOCode3('BES'),
			StoreCountry::create('IO', 'Британська територія в Індійському океані')->setISOCode3('IOT'),
			StoreCountry::create('VG', 'Британські Віргінські острови')->setISOCode3('VGB'),
			StoreCountry::create('BN', 'Бруней')->setISOCode3('BRN'),
			StoreCountry::create('BG', 'Болгарія')->setISOCode3('BGR'),
			StoreCountry::create('BF', 'Буркіна-Фасо')->setISOCode3('BFA'),
			StoreCountry::create('BI', 'Бурунді')->setISOCode3('BDI'),
			StoreCountry::create('KH', 'Камбоджа')->setISOCode3('KHM'),
			StoreCountry::create('CM', 'Камерун')->setISOCode3('CMR'),
			StoreCountry::create('CA', 'Канада')->setISOCode3('CAN')
				->addRegion(new StoreRegion('ON', 'Онтаріо'))
				->addRegion(new StoreRegion('QC', 'Квебек'))
				->addRegion(new StoreRegion('NS', 'Нова Шотландія'))
				->addRegion(new StoreRegion('NB', 'Нью-Брансвік'))
				->addRegion(new StoreRegion('MB', 'Манітоба'))
				->addRegion(new StoreRegion('BC', 'Британська Колумбія'))
				->addRegion(new StoreRegion('PE', 'Острів Принца Едуарда'))
				->addRegion(new StoreRegion('SK', 'Саскачеван'))
				->addRegion(new StoreRegion('AB', 'Альберта'))
				->addRegion(new StoreRegion('NL', 'Ньюфаундленд і Лабрадор'))
				->addRegion(new StoreRegion('NT', 'Північно-Західні території'))
				->addRegion(new StoreRegion('YT', 'Юкон'))
				->addRegion(new StoreRegion('NU', 'Нунавут')),
			StoreCountry::create('CV', 'Кабо Верде')->setISOCode3('CPV'),
			StoreCountry::create('KY', 'Кайманові острови')->setISOCode3('CYM'),
			StoreCountry::create('CF', 'Центральноафриканська Республіка')->setISOCode3('CAF'),
			StoreCountry::create('TD', 'Чад')->setISOCode3('TCD'),
			StoreCountry::create('CL', 'Чилі')->setISOCode3('CHL'),
			StoreCountry::create('CN', 'Китай')->setISOCode3('CHN'),
			StoreCountry::create('CX', 'Острів Різдва')->setISOCode3('CXR'),
			StoreCountry::create('CO', 'Колумбія')->setISOCode3('COL'),
			StoreCountry::create('KM', 'Коморські острови')->setISOCode3('COM'),
			StoreCountry::create('CG', 'Конго – Браззавіль')->setISOCode3('COG'),
			StoreCountry::create('CD', 'Конго – Кіншаса')->setISOCode3('COD'),
			StoreCountry::create('CK', 'Острови Кука')->setISOCode3('COK'),
			StoreCountry::create('CR', 'Коста-Рика')->setISOCode3('CRI'),
			StoreCountry::create('CI', 'Кот-д’Івуар')->setISOCode3('CIV'),
			StoreCountry::create('HR', 'Хорватія')->setISOCode3('HRV'),
			StoreCountry::create('CU', 'Куба')->setISOCode3('CUB'),
			StoreCountry::create('CY', 'Кіпр')->setISOCode3('CYP'),
			StoreCountry::create('CZ', 'Чехія')->setISOCode3('CZE'),
			StoreCountry::create('DK', 'Данія')->setISOCode3('DNK'),
			StoreCountry::create('DJ', 'Джибуті')->setISOCode3('DJI'),
			StoreCountry::create('DM', 'Домініка')->setISOCode3('DMA'),
			StoreCountry::create('DO', 'Домініканська Республіка')->setISOCode3('DOM'),
			StoreCountry::create('EC', 'Еквадор')->setISOCode3('ECU'),
			StoreCountry::create('EG', 'Єгипет')->setISOCode3('EGY'),
			StoreCountry::create('SV', 'Сальвадор')->setISOCode3('SLV'),
			StoreCountry::create('GQ', 'Екваторіальна Гвінея')->setISOCode3('GNQ'),
			StoreCountry::create('ER', 'Еритрея')->setISOCode3('ERI'),
			StoreCountry::create('EE', 'Естонія')->setISOCode3('EST'),
			StoreCountry::create('ET', 'Ефіопія')->setISOCode3('ETH'),
			StoreCountry::create('FK', 'Фолклендські острови')->setISOCode3('FLK'),
			StoreCountry::create('FO', 'Фарерські острови')->setISOCode3('FRO'),
			StoreCountry::create('FJ', 'Фіджі')->setISOCode3('FJI'),
			StoreCountry::create('FI', 'Фінляндія')->setISOCode3('FIN'),
			StoreCountry::create('FR', 'Франція')->setISOCode3('FRA'),
			StoreCountry::create('GF', 'Французька Гвіана')->setISOCode3('GUF'),
			StoreCountry::create('PF', 'Французька Полінезія')->setISOCode3('PYF'),
			StoreCountry::create('TF', 'Французькі Південні Території')->setISOCode3('ATF'),
			StoreCountry::create('GA', 'Габон')->setISOCode3('GAB'),
			StoreCountry::create('GM', 'Гамбія')->setISOCode3('GMB'),
			StoreCountry::create('GE', 'Грузія')->setISOCode3('GEO'),
			StoreCountry::create('DE', 'Німеччина')->setISOCode3('DEU'),
			StoreCountry::create('GH', 'Гана')->setISOCode3('GHA'),
			StoreCountry::create('GI', 'Гібралтар')->setISOCode3('GIB'),
			StoreCountry::create('GR', 'Греція')->setISOCode3('GRC'),
			StoreCountry::create('GL', 'Гренландія')->setISOCode3('GRL'),
			StoreCountry::create('GD', 'Гренада')->setISOCode3('GRD'),
			StoreCountry::create('GP', 'Гваделупа')->setISOCode3('GLP'),
			StoreCountry::create('GU', 'Гуам')->setISOCode3('GUM'),
			StoreCountry::create('GT', 'Гватемала')->setISOCode3('GTM'),
			StoreCountry::create('GG', 'Гернсі')->setISOCode3('GGY'),
			StoreCountry::create('GN', 'Гвінея')->setISOCode3('GIN'),
			StoreCountry::create('GW', 'Гвінея-Бісау')->setISOCode3('GNB'),
			StoreCountry::create('GY', 'Гайана')->setISOCode3('GUY'),
			StoreCountry::create('HT', 'Гаїті')->setISOCode3('HTI'),
			StoreCountry::create('HM', 'Острів Херд і острови Макдональд')->setISOCode3('HMD'),
			StoreCountry::create('HN', 'Гондурас')->setISOCode3('HND'),
			StoreCountry::create('HK', 'Гонконг, О.А.Р. Китаю')->setISOCode3('HKG'),
			StoreCountry::create('HU', 'Угорщина')->setISOCode3('HUN'),
			StoreCountry::create('IS', 'Ісландія')->setISOCode3('ISL'),
			StoreCountry::create('IN', 'Індія')->setISOCode3('IND'),
			StoreCountry::create('ID', 'Індонезія')->setISOCode3('IDN'),
			StoreCountry::create('IR', 'Іран')->setISOCode3('IRN'),
			StoreCountry::create('IQ', 'Ірак')->setISOCode3('IRQ'),
			StoreCountry::create('IE', 'Ірландія')->setISOCode3('IRL'),
			StoreCountry::create('IM', 'Острів Мен')->setISOCode3('IMN'),
			StoreCountry::create('IL', 'Ізраїль')->setISOCode3('ISR'),
			StoreCountry::create('IT', 'Італія')->setISOCode3('ITA'),
			StoreCountry::create('JM', 'Ямайка')->setISOCode3('JAM'),
			StoreCountry::create('JP', 'Японія')->setISOCode3('JPN'),
			StoreCountry::create('JE', 'Джерсі')->setISOCode3('JEY'),
			StoreCountry::create('JO', 'Йорданія')->setISOCode3('JOR'),
			StoreCountry::create('KZ', 'Казахстан')->setISOCode3('KAZ')
				->addRegion(new StoreRegion('ABA', 'Абайська область'))
				->addRegion(new StoreRegion('AKM', 'Акмолинська область'))
				->addRegion(new StoreRegion('AKT', 'Актюбінська область'))
				->addRegion(new StoreRegion('ALA', 'Алмати'))
				->addRegion(new StoreRegion('ALM', 'Алматинська область'))
				->addRegion(new StoreRegion('ATY', 'Атирауська область'))
				->addRegion(new StoreRegion('BAY', 'Байконур'))
				->addRegion(new StoreRegion('VOS', 'Східно-Казахстанська область'))
				->addRegion(new StoreRegion('ZHA', 'Жамбульська обл'))
				->addRegion(new StoreRegion('JET', 'Регіон Джетісу'))
				->addRegion(new StoreRegion('KAR', 'Карагандинська обл'))
				->addRegion(new StoreRegion('KUS', 'Костанайська обл'))
				->addRegion(new StoreRegion('KZY', 'Кизилординська обл'))
				->addRegion(new StoreRegion('MAN', 'Мангістауська обл'))
				->addRegion(new StoreRegion('SEV', 'Північно-Казахстанська область'))
				->addRegion(new StoreRegion('AST', 'Нур-Султан'))
				->addRegion(new StoreRegion('PAV', 'Павлодарська обл'))
				->addRegion(new StoreRegion('SHY', 'Шимкент'))
				->addRegion(new StoreRegion('YUZ', 'Туркестанська область'))
				->addRegion(new StoreRegion('ULY', 'Улитауська область'))
				->addRegion(new StoreRegion('ZAP', 'Західно-Казахстанська область')),
			StoreCountry::create('KE', 'Кенія')->setISOCode3('KEN'),
			StoreCountry::create('KI', 'Кірибаті')->setISOCode3('KIR'),
			StoreCountry::create('KW', 'Кувейт')->setISOCode3('KWT'),
			StoreCountry::create('KG', 'Киргизстан')->setISOCode3('KGZ'),
			StoreCountry::create('LA', 'Лаос')->setISOCode3('LAO'),
			StoreCountry::create('LV', 'Латвія')->setISOCode3('LVA'),
			StoreCountry::create('LB', 'Ліван')->setISOCode3('LBN'),
			StoreCountry::create('LS', 'Лесото')->setISOCode3('LSO'),
			StoreCountry::create('LR', 'Ліберія')->setISOCode3('LBR'),
			StoreCountry::create('LY', 'Лівія')->setISOCode3('LBY'),
			StoreCountry::create('LI', 'Ліхтенштейн')->setISOCode3('LIE'),
			StoreCountry::create('LT', 'Литва')->setISOCode3('LTU'),
			StoreCountry::create('LU', 'Люксембург')->setISOCode3('LUX'),
			StoreCountry::create('MO', 'Макао О.А.Р. Китаю')->setISOCode3('MAC'),
			StoreCountry::create('MK', 'Північна Македонія')->setISOCode3('MKD'),
			StoreCountry::create('MG', 'Мадагаскар')->setISOCode3('MDG'),
			StoreCountry::create('MW', 'Малаві')->setISOCode3('MWI'),
			StoreCountry::create('MY', 'Малайзія')->setISOCode3('MYS'),
			StoreCountry::create('MV', 'Мальдіви')->setISOCode3('MDV'),
			StoreCountry::create('ML', 'Малі')->setISOCode3('MLI'),
			StoreCountry::create('MT', 'Мальта')->setISOCode3('MLT'),
			StoreCountry::create('MH', 'Маршаллові острови')->setISOCode3('MHL'),
			StoreCountry::create('MQ', 'Мартініка')->setISOCode3('MTQ'),
			StoreCountry::create('MR', 'Мавританія')->setISOCode3('MRT'),
			StoreCountry::create('MU', 'Маврикій')->setISOCode3('MUS'),
			StoreCountry::create('YT', 'Майотта')->setISOCode3('MYT'),
			StoreCountry::create('MX', 'Мексика')->setISOCode3('MEX'),
			StoreCountry::create('FM', 'Мікронезія')->setISOCode3('FSM'),
			StoreCountry::create('MD', 'Молдова')->setISOCode3('MDA'),
			StoreCountry::create('MC', 'Монако')->setISOCode3('MCO'),
			StoreCountry::create('MN', 'Монголія')->setISOCode3('MNG'),
			StoreCountry::create('ME', 'Чорногорія')->setISOCode3('MNE'),
			StoreCountry::create('MS', 'Монсеррат')->setISOCode3('MSR'),
			StoreCountry::create('MA', 'Марокко')->setISOCode3('MAR'),
			StoreCountry::create('MZ', 'Мозамбік')->setISOCode3('MOZ'),
			StoreCountry::create('MM', 'Мʼянма (Бірма)')->setISOCode3('MMR'),
			StoreCountry::create('NA', 'Намібія')->setISOCode3('NAM'),
			StoreCountry::create('NR', 'Науру')->setISOCode3('NRU'),
			StoreCountry::create('NP', 'Непал')->setISOCode3('NPL'),
			StoreCountry::create('NL', 'Нідерланди')->setISOCode3('NLD'),
			StoreCountry::create('NC', 'Нова Каледонія')->setISOCode3('NCL'),
			StoreCountry::create('NZ', 'Нова Зеландія')->setISOCode3('NZL'),
			StoreCountry::create('NI', 'Нікарагуа')->setISOCode3('NIC'),
			StoreCountry::create('NE', 'Нігер')->setISOCode3('NER'),
			StoreCountry::create('NG', 'Нігерія')->setISOCode3('NGA')
				->addRegion(new StoreRegion('AB', 'Abia'))
				->addRegion(new StoreRegion('AD', 'Adamawa'))
				->addRegion(new StoreRegion('AK', 'Akwa Ibom'))
				->addRegion(new StoreRegion('AN', 'Anambra'))
				->addRegion(new StoreRegion('BA', 'Bauchi'))
				->addRegion(new StoreRegion('BY', 'Bayelsa'))
				->addRegion(new StoreRegion('BE', 'Benue'))
				->addRegion(new StoreRegion('BO', 'Borno'))
				->addRegion(new StoreRegion('CR', 'Cross River'))
				->addRegion(new StoreRegion('DE', 'Delta'))
				->addRegion(new StoreRegion('EB', 'Ebonyi'))
				->addRegion(new StoreRegion('ED', 'Edo'))
				->addRegion(new StoreRegion('EK', 'Ekiti'))
				->addRegion(new StoreRegion('EN', 'Enugu'))
				->addRegion(new StoreRegion('GO', 'Gombe'))
				->addRegion(new StoreRegion('IM', 'Imo'))
				->addRegion(new StoreRegion('JI', 'Jigawa'))
				->addRegion(new StoreRegion('KD', 'Kaduna'))
				->addRegion(new StoreRegion('KN', 'Kano'))
				->addRegion(new StoreRegion('KT', 'Katsina'))
				->addRegion(new StoreRegion('KE', 'Kebbi'))
				->addRegion(new StoreRegion('KO', 'Kogi'))
				->addRegion(new StoreRegion('KW', 'Kwara'))
				->addRegion(new StoreRegion('LA', 'Lagos'))
				->addRegion(new StoreRegion('NA', 'Nasarawa'))
				->addRegion(new StoreRegion('NI', 'Niger'))
				->addRegion(new StoreRegion('OG', 'Ogun'))
				->addRegion(new StoreRegion('ON', 'Ondo'))
				->addRegion(new StoreRegion('OS', 'Osun'))
				->addRegion(new StoreRegion('OY', 'Oyo'))
				->addRegion(new StoreRegion('PL', 'Plateau'))
				->addRegion(new StoreRegion('RI', 'Rivers'))
				->addRegion(new StoreRegion('SO', 'Sokoto'))
				->addRegion(new StoreRegion('TA', 'Taraba'))
				->addRegion(new StoreRegion('YO', 'Yobe'))
				->addRegion(new StoreRegion('ZA', 'Zamfara')),
			StoreCountry::create('NU', 'Ніуе')->setISOCode3('NIU'),
			StoreCountry::create('NF', 'Острів Норфолк')->setISOCode3('NFK'),
			StoreCountry::create('KP', 'Північна Корея')->setISOCode3('PRK'),
			StoreCountry::create('MP', 'Північні Маріанські острови')->setISOCode3('MNP'),
			StoreCountry::create('NO', 'Норвегія')->setISOCode3('NOR'),
			StoreCountry::create('OM', 'Оман')->setISOCode3('OMN'),
			StoreCountry::create('PK', 'Пакистан')->setISOCode3('PAK'),
			StoreCountry::create('PW', 'Палау')->setISOCode3('PLW'),
			StoreCountry::create('PS', 'Palestinian Territories')->setISOCode3('PSE'),
			StoreCountry::create('PA', 'Панама')->setISOCode3('PAN'),
			StoreCountry::create('PG', 'Папуа-Нова Гвінея')->setISOCode3('PNG'),
			StoreCountry::create('PY', 'Парагвай')->setISOCode3('PRY'),
			StoreCountry::create('PE', 'Перу')->setISOCode3('PER'),
			StoreCountry::create('PH', 'Філіппіни')->setISOCode3('PHL'),
			StoreCountry::create('PL', 'Польща')->setISOCode3('POL'),
			StoreCountry::create('PT', 'Португалія')->setISOCode3('PRT'),
			StoreCountry::create('PR', 'Пуерто-Рико')->setISOCode3('PRI'),
			StoreCountry::create('QA', 'Катар')->setISOCode3('QAT'),
			StoreCountry::create('RE', 'Реюньйон')->setISOCode3('REU'),
			StoreCountry::create('RO', 'Румунія')->setISOCode3('ROU'),
			StoreCountry::create('RU', 'Росія')->setISOCode3('RUS'),
			StoreCountry::create('RW', 'Руанда')->setISOCode3('RWA'),
			StoreCountry::create('BL', 'Сен-Бартельмі')->setISOCode3('BLM'),
			StoreCountry::create('SH', 'Острів Святої Єлени')->setISOCode3('SHN'),
			StoreCountry::create('KN', 'Сент-Кітс і Невіс')->setISOCode3('KNA'),
			StoreCountry::create('LC', 'Сент-Люсія')->setISOCode3('LCA'),
			StoreCountry::create('MF', 'Сен-Мартен')->setISOCode3('MAF'),
			StoreCountry::create('PM', 'Сен-Пʼєр і Мікелон')->setISOCode3('SPM'),
			StoreCountry::create('VC', 'Сент-Вінсент і Гренадини')->setISOCode3('VCT'),
			StoreCountry::create('WS', 'Самоа')->setISOCode3('WSM'),
			StoreCountry::create('SM', 'Сан-Марино')->setISOCode3('SMR'),
			StoreCountry::create('ST', 'Сан-Томе і Прінсіпі')->setISOCode3('STP'),
			StoreCountry::create('SA', 'Саудівська Аравія')->setISOCode3('SAU'),
			StoreCountry::create('SN', 'Сенегал')->setISOCode3('SEN'),
			StoreCountry::create('RS', 'Сербія')->setISOCode3('SRB'),
			StoreCountry::create('SC', 'Сейшельські острови')->setISOCode3('SYC'),
			StoreCountry::create('SL', 'Сьєрра-Леоне')->setISOCode3('SLE'),
			StoreCountry::create('SG', 'Сінгапур')->setISOCode3('SGP'),
			StoreCountry::create('SK', 'Словаччина')->setISOCode3('SVK'),
			StoreCountry::create('SI', 'Словенія')->setISOCode3('SVN'),
			StoreCountry::create('SB', 'Соломонові Острови')->setISOCode3('SLB'),
			StoreCountry::create('SO', 'Сомалі')->setISOCode3('SOM'),
			StoreCountry::create('ZA', 'Південна Африка')->setISOCode3('ZAF'),
			StoreCountry::create('GS', 'Південна Джорджія та Південні Сандвічеві острови')->setISOCode3('SGS'),
			StoreCountry::create('KR', 'Південна Корея')->setISOCode3('KOR'),
			StoreCountry::create('ES', 'Іспанія')->setISOCode3('ESP')
				->addRegion(new StoreRegion('VI', 'Álava'))
				->addRegion(new StoreRegion('AB', 'Albacete'))
				->addRegion(new StoreRegion('A', 'Alicante'))
				->addRegion(new StoreRegion('AL', 'Almería'))
				->addRegion(new StoreRegion('O', 'Asturias'))
				->addRegion(new StoreRegion('AV', 'Ávila'))
				->addRegion(new StoreRegion('BA', 'Badajoz'))
				->addRegion(new StoreRegion('B', 'Barcelona'))
				->addRegion(new StoreRegion('BU', 'Burgos'))
				->addRegion(new StoreRegion('CC', 'Cáceres'))
				->addRegion(new StoreRegion('CA', 'Cádiz'))
				->addRegion(new StoreRegion('S', 'Cantabria'))
				->addRegion(new StoreRegion('CS', 'Castellón de la Plana'))
				->addRegion(new StoreRegion('CE', 'Ceuta'))
				->addRegion(new StoreRegion('CR', 'Ciudad Real'))
				->addRegion(new StoreRegion('CO', 'Córdoba'))
				->addRegion(new StoreRegion('CU', 'Cuenca'))
				->addRegion(new StoreRegion('GI', 'Gerona'))
				->addRegion(new StoreRegion('GR', 'Granada'))
				->addRegion(new StoreRegion('GU', 'Guadalajara'))
				->addRegion(new StoreRegion('SS', 'Guipúzcoa'))
				->addRegion(new StoreRegion('H', 'Huelva'))
				->addRegion(new StoreRegion('HU', 'Huesca'))
				->addRegion(new StoreRegion('PM', 'Islas Baleares'))
				->addRegion(new StoreRegion('J', 'Jaén'))
				->addRegion(new StoreRegion('C', 'La Coruña'))
				->addRegion(new StoreRegion('LO', 'La Rioja'))
				->addRegion(new StoreRegion('GC', 'Las Palmas (Islas Canarias)'))
				->addRegion(new StoreRegion('LE', 'León'))
				->addRegion(new StoreRegion('L', 'Lérida'))
				->addRegion(new StoreRegion('LU', 'Lugo'))
				->addRegion(new StoreRegion('M', 'Madrid'))
				->addRegion(new StoreRegion('MA', 'Málaga'))
				->addRegion(new StoreRegion('ML', 'Melilla'))
				->addRegion(new StoreRegion('MU', 'Murcia'))
				->addRegion(new StoreRegion('NA', 'Navarra'))
				->addRegion(new StoreRegion('OR', 'Orense'))
				->addRegion(new StoreRegion('P', 'Palencia'))
				->addRegion(new StoreRegion('PO', 'Pontevedra'))
				->addRegion(new StoreRegion('SA', 'Salamanca'))
				->addRegion(new StoreRegion('TF', 'Santa Cruz de Tenerife (Islas Canarias)'))
				->addRegion(new StoreRegion('SG', 'Segovia'))
				->addRegion(new StoreRegion('SE', 'Sevilla'))
				->addRegion(new StoreRegion('SO', 'Soria'))
				->addRegion(new StoreRegion('T', 'Tarragona'))
				->addRegion(new StoreRegion('TE', 'Teruel'))
				->addRegion(new StoreRegion('TO', 'Toledo'))
				->addRegion(new StoreRegion('V', 'Valencia'))
				->addRegion(new StoreRegion('VA', 'Valladolid'))
				->addRegion(new StoreRegion('BI', 'Vizcaya'))
				->addRegion(new StoreRegion('ZA', 'Zamora'))
				->addRegion(new StoreRegion('Z', 'Zaragoza')),
			StoreCountry::create('LK', 'Шрі-Ланка')->setISOCode3('LKA'),
			StoreCountry::create('SD', 'Судан')->setISOCode3('SDN'),
			StoreCountry::create('SR', 'Сурінам')->setISOCode3('SUR'),
			StoreCountry::create('SZ', 'Есватіні (Свазіленд)')->setISOCode3('SWZ'),
			StoreCountry::create('SE', 'Швеція')->setISOCode3('SWE'),
			StoreCountry::create('CH', 'Швейцарія')->setISOCode3('CHE'),
			StoreCountry::create('SY', 'Сирія')->setISOCode3('SYR'),
			StoreCountry::create('TW', 'Тайвань')->setISOCode3('TWN'),
			StoreCountry::create('TJ', 'Таджикистан')->setISOCode3('TJK'),
			StoreCountry::create('TZ', 'Танзанія')->setISOCode3('TZA'),
			StoreCountry::create('TH', 'Таїланд')->setISOCode3('THA'),
			StoreCountry::create('TL', 'Східний Тимор')->setISOCode3('TLS'),
			StoreCountry::create('TG', 'Того')->setISOCode3('TGO'),
			StoreCountry::create('TK', 'Токелау')->setISOCode3('TKL'),
			StoreCountry::create('TO', 'Тонга')->setISOCode3('TON'),
			StoreCountry::create('TT', 'Тринідад і Тобаго')->setISOCode3('TTO'),
			StoreCountry::create('TN', 'Туніс')->setISOCode3('TUN'),
			StoreCountry::create('TR', 'Туреччина')->setISOCode3('TUR'),
			StoreCountry::create('TM', 'Туркменістан')->setISOCode3('TKM'),
			StoreCountry::create('TC', 'Острови Теркс і Кайкос')->setISOCode3('TCA'),
			StoreCountry::create('TV', 'Тувалу')->setISOCode3('TUV'),
			StoreCountry::create('UM', 'Віддалені острови США')->setISOCode3('UMI'),
			StoreCountry::create('VI', 'Віргінські острови, США')->setISOCode3('VIR'),
			StoreCountry::create('UG', 'Уганда')->setISOCode3('UGA'),
			StoreCountry::create('UA', 'Україна')->setISOCode3('UKR'),
			StoreCountry::create('AE', 'Обʼєднані Арабські Емірати')->setISOCode3('ARE'),
			StoreCountry::create('GB', 'Велика Британія')->setISOCode3('GBR'),
			StoreCountry::create('US', 'Сполучені Штати')->setISOCode3('USA')
				->addRegion(new StoreRegion('AL', 'Алабама'))
				->addRegion(new StoreRegion('AK', 'Аляска'))
				->addRegion(new StoreRegion('AZ', 'Арізона'))
				->addRegion(new StoreRegion('AR', 'Арканзас'))
				->addRegion(new StoreRegion('CA', 'Каліфорнія'))
				->addRegion(new StoreRegion('CO', 'Колорадо'))
				->addRegion(new StoreRegion('CT', 'Коннектикут'))
				->addRegion(new StoreRegion('DE', 'Делавер'))
				->addRegion(new StoreRegion('FL', 'Флорида'))
				->addRegion(new StoreRegion('GA', 'Грузія'))
				->addRegion(new StoreRegion('HI', 'Гаваї'))
				->addRegion(new StoreRegion('ID', 'Айдахо'))
				->addRegion(new StoreRegion('IL', 'Іллінойс'))
				->addRegion(new StoreRegion('IN', 'Індіана'))
				->addRegion(new StoreRegion('IA', 'Айова'))
				->addRegion(new StoreRegion('KS', 'Канзас'))
				->addRegion(new StoreRegion('KY', 'Кентуккі'))
				->addRegion(new StoreRegion('LA', 'Луїзіана'))
				->addRegion(new StoreRegion('ME', 'Мен'))
				->addRegion(new StoreRegion('MD', 'Меріленд'))
				->addRegion(new StoreRegion('MA', 'Массачусетс'))
				->addRegion(new StoreRegion('MI', 'Мічиган'))
				->addRegion(new StoreRegion('MN', 'Міннесота'))
				->addRegion(new StoreRegion('MS', 'Міссісіпі'))
				->addRegion(new StoreRegion('MO', 'Міссурі'))
				->addRegion(new StoreRegion('MT', 'Монтана'))
				->addRegion(new StoreRegion('NE', 'Небраска'))
				->addRegion(new StoreRegion('NV', 'Невада'))
				->addRegion(new StoreRegion('NH', 'Нью-Гемпшир'))
				->addRegion(new StoreRegion('NJ', 'Нью Джерсі'))
				->addRegion(new StoreRegion('NM', 'Нью-Мексико'))
				->addRegion(new StoreRegion('NY', 'Нью-Йорк'))
				->addRegion(new StoreRegion('NC', 'Північна Кароліна'))
				->addRegion(new StoreRegion('ND', 'Північна Дакота'))
				->addRegion(new StoreRegion('OH', 'Огайо'))
				->addRegion(new StoreRegion('OK', 'Оклахома'))
				->addRegion(new StoreRegion('OR', 'Орегон'))
				->addRegion(new StoreRegion('PA', 'Пенсильванія'))
				->addRegion(new StoreRegion('RI', 'Род-Айленд'))
				->addRegion(new StoreRegion('SC', 'Південна Кароліна'))
				->addRegion(new StoreRegion('SD', 'Південна Дакота'))
				->addRegion(new StoreRegion('TN', 'штат Теннессі'))
				->addRegion(new StoreRegion('TX', 'Техас'))
				->addRegion(new StoreRegion('UT', 'Юта'))
				->addRegion(new StoreRegion('VT', 'Вермонт'))
				->addRegion(new StoreRegion('VA', 'Вірджинія'))
				->addRegion(new StoreRegion('WA', 'Вашингтон'))
				->addRegion(new StoreRegion('DC', 'Вашингтон (округ Колумбія)'))
				->addRegion(new StoreRegion('WV', 'Західна Вірджинія'))
				->addRegion(new StoreRegion('WI', 'Вісконсін'))
				->addRegion(new StoreRegion('WY', 'Вайомінг')),
			StoreCountry::create('UY', 'Уругвай')->setISOCode3('URY'),
			StoreCountry::create('UZ', 'Узбекистан')->setISOCode3('UZB'),
			StoreCountry::create('VU', 'Вануату')->setISOCode3('VUT'),
			StoreCountry::create('VA', 'Ватикан')->setISOCode3('VAT'),
			StoreCountry::create('VE', 'Венесуела')->setISOCode3('VEN'),
			StoreCountry::create('VN', 'Вʼєтнам')->setISOCode3('VNM'),
			StoreCountry::create('WF', 'Волліс і Футуна')->setISOCode3('WLF'),
			StoreCountry::create('EH', 'Західна Сахара')->setISOCode3('ESH'),
			StoreCountry::create('YE', 'Ємен')->setISOCode3('YEM'),
			StoreCountry::create('ZM', 'Замбія')->setISOCode3('ZMB'),
			StoreCountry::create('ZW', 'Зімбабве')->setISOCode3('ZWE')
		);
		usort($list, function(StoreCountry $a, StoreCountry $b) {
			return ($a->name > $b->name) ? 1 : -1;
		});
		return $list;
	}
	
}
