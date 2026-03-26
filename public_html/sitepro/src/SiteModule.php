<?php

class SiteModule {
	
	/** @var SiteInfo */
	public static $siteInfo;
	/** @var string|null */
	public static $lang = null;
	/** @var string|null */
	public static $baseLang = null;
	/** @var string */
	private static $preferredLang;
	/** @var array */
	private static $translations;
	/** @var ?object */
	private static $injectAdsData = null;
	
	public static function init($none, SiteInfo $siteInfo) {
		self::$siteInfo = $siteInfo;
	}
	
	/**
	 * @param ?string $lang
	 * @param ?string $baseLang
	 */
	public static function setLang($lang, $baseLang = null) {
		self::$lang = $lang;
		if (is_string($baseLang) && !empty($baseLang)) self::$baseLang = $baseLang;
	}
	
	public static function getPreferredLang() {
		if (!self::$preferredLang) {
			/* @var $siteInfo SiteInfo */
			$siteInfo = self::$siteInfo ? self::$siteInfo : new SiteInfo();
			self::$preferredLang = self::$lang ? self::$lang : ($siteInfo->defLang ? $siteInfo->defLang : $siteInfo->baseLang);
		}
		return self::$preferredLang;
	}
	
	public static function initTranslations(array $translations) {
		self::$translations = $translations;
	}
	
	public static function __($key, $langKey = null) {
		if (!$langKey) $langKey = self::$lang ? self::$lang : '-';
		$translated = $key;
		if (self::$translations && isset(self::$translations[$langKey][$key]) && self::$translations[$langKey][$key]) {
			$translated = self::$translations[$langKey][$key];
		} else if ($langKey != '-' && self::$translations && isset(self::$translations['-'][$key]) && self::$translations['-'][$key]) {
			$translated = self::$translations['-'][$key];
		}
		return $translated;
	}
	
	/**
	 * @param object $data
	 * @return void
	 */
	public static function setInjectAdsData($data) {
		self::$injectAdsData = $data;
	}

	/** @return ?object */
	public static function getInjectAdsData() {
		return self::$injectAdsData;
	}
}
