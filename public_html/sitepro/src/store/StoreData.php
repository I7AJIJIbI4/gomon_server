<?php

use Profis\SitePro\controller\StoreDataCurrency;
use Profis\SitePro\controller\StoreDataDestinationZone;
use Profis\SitePro\controller\StoreDataItem;

class StoreData {
	/** @var \Profis\SitePro\controller\StoreModuleSiteData|null */
	private static $data;
	/** @var \Profis\SitePro\controller\StoreDataCategory[] */
	private static $categoryIdx;
	/** @var \Profis\SitePro\controller\StoreDataItemType[] */
	private static $itemTypeIdx;
	/** @var \Profis\SitePro\controller\StoreDataItemFieldType[] */
	private static $itemFieldTypeIdx;
	/** @var \Profis\SitePro\controller\StoreDataItem[]|null */
	private static $itemIdx = null;

	private static function getDataFile() {
		return dirname(__FILE__).'/store.dat';
	}

	/** @return \Profis\SitePro\controller\StoreModuleData */
	private static function getData() {
		if (!self::$data) {
			$dataFile = self::getDataFile();
			if (is_file($dataFile)) {
				$data = json_decode(file_get_contents($dataFile));
				/** @var \Profis\SitePro\controller\StoreModuleData|null $data */
				if ($data) {
					$data->itemStockChangesApplied = false;
				}
				self::$data = $data;
				self::$itemIdx = null;
			}
		}
		return self::$data;
	}
	
	public static function randomHash($len = 17, $onlyDigits = false) {
		return randomHash($len, $onlyDigits);
	}

	/**
	 * @param mixed $value
	 * @param bool $withFallback
	 * @return bool
	 */
	public static function isUID($value, $withFallback = false) {
		if (is_string($value) && preg_match('#^[a-f0-9]{32}$#', $value)) {
			return true;
		} else if ($withFallback && is_numeric($value) && $value > 0) {
			return true;
		} else {
			return false;
		}
	}

	/** @return bool */
	public static function needToShowDates() {
		return (($data = self::getData()) && isset($data->showDates) && $data->showDates);
	}
	
	/** @return bool */
	public static function needToShowItemId() {
		return (($data = self::getData()) && isset($data->showItemId) && $data->showItemId);
	}
	
	/**
	 * Format price to price string.
	 * @param float $price price to format.
	 * @param StorePriceOptions  $priceOptions
	 * @param StoreCurrency|StoreDataCurrency|null $currency
	 * @return string
	 */
	public static function formatPrice($price, StorePriceOptions $priceOptions, $currency = null) {
		return (($currency ? $currency->prefix : '')
				.number_format($price, intval($priceOptions->decimalPlaces), $priceOptions->decimalPoint, $priceOptions->thousandsSeparator)
				.($currency ? $currency->postfix : ''));
	}
	
	/**
	 * Get cart item quantity.
	 * @param \Profis\SitePro\controller\StoreDataItem|StoreModuleOrderItem $item
	 * @return int
	 */
	public static function cartItemQuantity($item) {
		if (!$item) return 0;
		return ((isset($item->quantity) && is_numeric($item->quantity) && intval($item->quantity) > 0) ? intval($item->quantity) : 1);
	}
	
	/**
	 * Get total cart item count.
	 * @return int
	 */
	public static function countCartItems() {
		$cartData = self::getCartData();
		$total = 0;
		foreach ($cartData->items as $item) {
			$total += self::cartItemQuantity($item);
		}
		return $total;
	}
	
	/**
	 * @param float $defaultTaxRate
	 * @return StoreCartData
	 */
	public static function getCartData($defaultTaxRate = -1) {
		if (!session_id()) @session_start();
		$data = isset($_SESSION[StoreModule::$sessionKey])
			? StoreCartData::fromJson($_SESSION[StoreModule::$sessionKey])
			: null;
		if (!$data) $data = new StoreCartData();

		$updatedItems = array();
		foreach ($data->items as $cartItem) {
			$item = self::findItemById($cartItem->id);
			if (!$item) continue;
			$updatedItem = clone $item;

			$variant = self::detectItemVariant($updatedItem, $cartItem);
			if ($variant) {
				$updatedItem->cartId = self::applyItemVariant($updatedItem, $variant);
			} else {
				$updatedItem->cartId = $updatedItem->id;
			}
			if ($cartItem->stockManaged && $updatedItem->quantity <= 0) continue;

			$defaultTaxRateFull = 1 + (($defaultTaxRate >= 0) ? $defaultTaxRate : StoreData::getDefaultTaxRateWithIncluded($updatedItem->itemType));
			$updatedItem->fullPrice = $updatedItem->price * $defaultTaxRateFull;
			list($updatedItem->price) = self::applyPriceDiscount($updatedItem, null, $updatedItem->price);
			$updatedItem->price *= $defaultTaxRateFull;

			if (!$cartItem->stockManaged || ($cartItem->quantity <= $updatedItem->quantity)) {
				$updatedItem->quantity = $cartItem->quantity;
			}

			$updatedItems[] = $updatedItem;
		}
		$data->items = $updatedItems;

		return $data;
	}
	
	/**
	 * @param StoreCartData $data
	 */
	public static function setCartData(StoreCartData $data) {
		if (!session_id()) @session_start();
		$_SESSION[StoreModule::$sessionKey] = json_encode($data->jsonSerialize());
	}
	
	public static function storeFilters($pageId, $filters) {
		if (!session_id()) @session_start();
		$_SESSION[StoreModule::$sessionKey.'_filters_'.$pageId] = $filters;
	}
	
	public static function loadFilters($pageId) {
		if (!session_id()) @session_start();
		$key = StoreModule::$sessionKey.'_filters_'.$pageId;
		$filters = isset($_SESSION[$key]) ? $_SESSION[$key] : null;
		if (!is_array($filters)) $filters = array();
		return $filters;
	}
	
	/**
	 * @param int $itemType
	 * @param bool $useIncluded
	 * @return float
	 */
	public static function getDefaultTaxRate($itemType, $useIncluded = false) {
		$rateVal = 0;
		$defaultTax = self::getDefaultTaxSettings();
		if ($defaultTax && $defaultTax->enabled && (!$useIncluded || ($useIncluded && !$defaultTax->taxIncluded)) ) {
			$destinationZoneId = $defaultTax->destinationZoneId;
			foreach (self::getTaxRules() as $rule) {
				if (!$rule->appliesToProducts
					|| (!empty($rule->categoryId) && $rule->categoryId != $itemType)) {
					continue;
				}
				foreach ($rule->rates as $rate) {
					if ($rate->destinationZoneId == $destinationZoneId) {
						$rateVal += $rate->rate;
						break;
					}
				}
			}
		}
		return $rateVal / 100;
	}

	/**
	 * @param int $itemType
	 * @return float
	 */
	public static function getDefaultTaxRateWithIncluded($itemType) {
		return self::getDefaultTaxRate($itemType, true);
	}

	/** @return \Profis\SitePro\controller\StoreDataTaxRule[] */
	public static function getTaxRules(StoreBillingInfo $billingInfo = null) {
		if (($data = self::getData()) && isset($data->taxRules) && is_array($data->taxRules)) {
			$zoneIdx = array();

			if ($billingInfo) {
				$zones = self::getDestinationZones($billingInfo);
				
				// Index zone specificities (lower value means more specific) by ID
				foreach ($zones as $zone) {
					$numZones = count($zone->countries);
					// Make world zone least specific
					if ($zone->id == -1) $numZones = 999999;
					$zoneIdx[(string) $zone->id] = $numZones;
				}
			}

			$list = array();
			foreach ($data->taxRules as $li) {
				if (!isset($li->categoryId) || !self::isUID($li->categoryId, true)) {
					$li->categoryId = '';
				} else {
					$li->categoryId = (string) $li->categoryId;
				}
				if (!isset($li->minOrderAmount) || !is_numeric($li->minOrderAmount)) {
					$li->minOrderAmount = 0;
				} else {
					$li->minOrderAmount = floatval($li->minOrderAmount);
				}
				if (!isset($li->appliesToProducts) || !is_bool($li->appliesToProducts)) {
					$li->appliesToProducts = true;
				}
				if (!isset($li->appliesToShipping) || !is_bool($li->appliesToProducts)) {
					$li->appliesToShipping = true;
				}
				if ($billingInfo) {
					$rule = null;
					$ruleSpecificity = 0;
					foreach ($li->rates as $rate) {
						if (!isset($zoneIdx[(string) $rate->destinationZoneId])) continue;
						if (!$rule || $ruleSpecificity > $zoneIdx[(string) $rate->destinationZoneId]) {
							$ruleSpecificity = $zoneIdx[(string) $rate->destinationZoneId];
							$rule = clone $li;
							$rule->rates = array($rate);
						}
					}
					if ($rule) $list[] = $rule;
				}
			}
			if ($billingInfo) {
				return $list;
			} else {
				return $data->taxRules;
			}
		}
		return array();
	}
	
	/** @return \Profis\SitePro\controller\StoreDataDestinationZone[] */
	public static function getDestinationZones(StoreBillingInfo $billingInfo = null) {
		if (($data = self::getData()) && isset($data->destinationZones) && is_array($data->destinationZones)) {
			if ($billingInfo) {
				$list = array();
				list($country, $region) = StoreCountry::findCountryAndRegion($billingInfo->countryCode, $billingInfo->region);
				foreach ($data->destinationZones as $li) {
					if ($li->id == "global") {
						$list[] = $li;
					} else if ($country && in_array($billingInfo->countryCode, $li->countries)) {
						$billingForm = static::getBillingForm();
						$regionRequired = false;
						if (isset($billingForm->content->fields)) {
							foreach ($billingForm->content->fields as $field) {
								if ($field->type == "wb_store_region" && $field->enabled) {
									$regionRequired = true;
								}
							}
						}
						$regionRequired &= !empty($country->regions);
						$regionFound = $regionRequired && $region && in_array($country->code . '-' . $region->code, $li->countries);
						if( $regionRequired && !$regionFound && $region ) {
							// We have to check if website creator has selected at least one region for this
							// country. If not treat it as if all regions are selected.
							$regionRequired = false;
							foreach( $li->countries as $code ) {
								if( preg_match("#^" . preg_quote($country->code) . "-#isu", $code) ) {
									$regionRequired = true;
									break;
								}
							}
						}
						if( !$regionRequired || $regionFound )
							$list[] = $li;
					}
				}
				return $list;
			}
			return $data->destinationZones;
		}
		return array();
	}
	
	/** @return \Profis\SitePro\controller\StoreDataShippingMethod[] */
	public static function getShippingMethods(StoreBillingInfo $billingInfo = null) {
		if (($data = self::getData()) && isset($data->shippingMethods) && is_array($data->shippingMethods)) {
			if ($billingInfo) {
				$zones = array_map(function($zone) { return $zone->id; }, self::getDestinationZones($billingInfo));
				$list = array();
				foreach ($data->shippingMethods as $li) {
					if (in_array($li->destinationZoneId, $zones)) $list[] = $li;
				}
				return $list;
			}
			return $data->shippingMethods;
		}
		return array();
	}

	public static function getAvailableShippingCountryAndRegionCodes() {
		$codes = array();
		if (($data = self::getData()) && isset($data->shippingMethods, $data->destinationZones) && is_array($data->shippingMethods) && is_array($data->destinationZones) ) {
			/** @var StoreDataDestinationZone[] $dzIndex */
			$dzIndex = array();
			foreach ($data->destinationZones as $zone) {
				if ($zone->id == "global") continue;
				$dzIndex[$zone->id] = $zone;
			}
			$countryIndex = array();
			foreach( StoreCountry::buildList() as $country )
				$countryIndex[$country->code] = $country;
			foreach( $data->shippingMethods as $method ) {
				if( $method->destinationZoneId && isset($dzIndex[$method->destinationZoneId]) ) {
					$zone = $dzIndex[$method->destinationZoneId];
					$zoneCodes = array();
					foreach( $zone->countries as $code ) {
						if( preg_match("#^([a-z]{2})-(.+)$#isu", $code, $mtc) ) {
							$countryCode = $mtc[1];
							$regionCode = $mtc[2];
						}
						else {
							$countryCode = $code;
							$regionCode = null;
						}
						if( !isset($codes[$countryCode]) )
							$codes[$countryCode] = array();
						if( $regionCode !== null )
							$codes[$countryCode][] = $regionCode;
						if( !isset($zoneCodes[$countryCode]) )
							$zoneCodes[$countryCode] = array();
						if( $regionCode !== null )
							$zoneCodes[$countryCode][] = $regionCode;
					}
					foreach( $zoneCodes as $countryCode => $regionCodes ) {
						if( empty($regionCodes) && isset($countryIndex[$countryCode]) && !empty($countryIndex[$countryCode]->regions) ) {
							// Zone has no regions selected, but country is selected. This must be treated as if all regions are selected.
							foreach( $countryIndex[$countryCode]->regions as $region )
								$codes[$countryCode][] = $region->code;
						}
					}
					unset($zoneCodes);
				} elseif ($method->destinationZoneId === 'global') {
					return [];
				}
			}
			foreach( $codes as $countryCode => $regionCodes )
				$codes[$countryCode] = array_values(array_unique($regionCodes));
		}
		return $codes;
	}

	/** @return \Profis\SitePro\controller\StoreDataCoupon[] */
	public static function getCoupons() {
		if (($data = self::getData()) && isset($data->coupons) && is_array($data->coupons)) {
			// Note: collect only valid and active coupons
			$now = date('Y-m-d');
			$result = array();
			foreach ($data->coupons as $li) {
				if (!isset($li->code) || !is_string($li->code)) {
					continue;
				}
				if (!isset($li->itemType) || !self::isUID($li->itemType, true)) {
					$li->itemType = '';
				} else {
					$li->itemType = (string) $li->itemType;
				}
				if (!isset($li->type) || !is_int($li->type)) {
					continue;
				}
				if (!isset($li->value) || !is_numeric($li->value)) {
					continue;
				} else {
					$li->value = floatval($li->value);
				}
				if (!isset($li->dateFrom) || !is_string($li->dateFrom) || !$li->dateFrom) {
					continue;
				}
				if (!isset($li->dateTo) || !is_string($li->dateTo) || !$li->dateTo || $li->dateTo < $li->dateFrom) {
					continue;
				}
				if ($li->dateFrom > $now || $li->dateTo < $now) {
					continue;
				}
				if (!isset($li->enabled) || !is_bool($li->enabled) || !$li->enabled) {
					continue;
				}
				if (!isset($li->applyToDiscounted) || !is_bool($li->applyToDiscounted)) {
					$li->applyToDiscounted = false;
				}
				if (!isset($li->description) || !is_string($li->description)) {
					$li->description = '';
				}
				$result[] = $li;
			}
			return $result;
		}
		return array();
	}

	/**
	 * @param string $code 
	 * @return ?\Profis\SitePro\controller\StoreDataCoupon
	 */
	public static function findCouponByCode($code) {
		foreach (self::getCoupons() as $c) {
			if ($c->code == $code) return $c;
		}
		return null;
	}

	/**
	 * @return ?\Profis\SitePro\controller\StoreDataCoupon
	 */
	public static function getActiveCoupon() {
		$cartData = StoreData::getCartData();
		if (!empty($cartData->couponCode)) {
			$coupons = StoreData::getCoupons();
			foreach ($coupons as $coupon) {
				if ($coupon->code == $cartData->couponCode) {
					return $coupon;
				}
			}
		}

		return false;
	}

	/** @return \Profis\SitePro\controller\StoreDataPaymentGateway[] */
	public static function getPaymentGateways() {
		if (($data = self::getData()) && isset($data->paymentGateways) && is_array($data->paymentGateways)) {
			return $data->paymentGateways;
		}
		return array();
	}
	
	/** @return bool */
	public static function getBillingShippingRequired() {
		if (($data = self::getData())) {
            $hasGateways = false;
            foreach (self::getPaymentGateways() as $gateway) {
                if ($gateway->enabled) {
                    $hasGateways = true;
                    break;
                }
            }
			return ($hasGateways && (!isset($data->billingShippingRequired) || $data->billingShippingRequired));
		}
		return false;
	}

	/** @return bool */
	public static function getDeliveryInfoRequired() {
		if (($data = self::getCartData(0))) {
            foreach ($data->items as $item) {
				if (!isset($item->shippingRequired) || $item->shippingRequired) {
					return true;
				}
            }
			return false;
		}
		return true;
	}
	
	/** @return \Profis\SitePro\controller\StoreImageData */
	public static function getNoPhotoImage() {
		if (($data = self::getData()) && isset($data->noPhotoImage) && $data->noPhotoImage) {
			return $data->noPhotoImage;
		}
		return null;
	}
	
	/** @return StorePriceOptions */
	public static function getPriceOptions() {
		if (($data = self::getData()) && isset($data->priceOptions) && is_object($data->priceOptions)) {
			return StorePriceOptions::fromJson($data->priceOptions);
		}
		return new StorePriceOptions();
	}
	
	/** @return StoreCurrency */
	public static function getCurrency() {
		if (($data = self::getData()) && isset($data->currency) && is_object($data->currency)) {
			return StoreCurrency::fromJson($data->currency);
		}
		return new StoreCurrency();
	}
	
	/**
	 * Get category indent from depth in category tree.
	 * @param \Profis\SitePro\controller\StoreDataCategory $category
	 * @param int $lvl indent of parent item.
	 * @return int
	 */
	private static function getCategoryIndent($category, $lvl = 0) {
		if (!$category || !isset($category->parentId) || !$category->parentId) return $lvl;
		$parent = self::getCategory($category->parentId);
		if (!$parent) return $lvl;
		return self::getCategoryIndent($parent, $lvl + 1);
	}
	
	/**
	 * @param bool $indent return indented category list.
	 * @return \Profis\SitePro\controller\StoreDataCategory[]
	 */
	public static function getCategories($indent = false) {
		if (($data = self::getData()) && isset($data->categories) && is_array($data->categories)) {
			if ($indent) {
				for ($i = 0, $c = count($data->categories); $i < $c; $i++) {
					$data->categories[$i]->indent = self::getCategoryIndent($data->categories[$i]);
				}
			}
			return $data->categories;
		}
		return array();
	}

	/** @return \Profis\SitePro\controller\StoreDataItem[] */
	public static function getItems() {
		if (($data = self::getData()) && isset($data->items) && is_array($data->items)) {
			if (!$data->itemStockChangesApplied) {
				$stockSettings = self::getStockSettings();
				if ($stockSettings) {
					list($stockChanges) = StoreModuleOrder::indexStockChanges($stockSettings->applyVersion);
				} else {
					$stockChanges = array();
				}

				foreach ($data->items as $item) {
					if (!isset($item->itemType) || !self::isUID($item->itemType, true)) {
						$item->itemType = '';
					} else {
						$item->itemType = (string) $item->itemType;
					}
					$item->cartId = '';
					if (!isset($item->price) || !is_numeric($item->price) || $item->price <= 0) {
						$item->price = 0;
					}
					if (!isset($item->discount) || !is_numeric($item->discount) || $item->discount < 0) {
						$item->discount = 0;
					} else if ($item->discount > 100) {
						$item->discount = 100;
					}
					$item->minFullPrice = $item->price;
					list(
						$item->minPrice,
						$item->minDiscount) = self::applyPriceDiscount($item, null, $item->price);
					if (!isset($item->sku) || !is_string($item->sku) || !$item->sku) {
						$item->sku = '';
					}
					if (!isset($item->quantity) || !is_numeric($item->quantity)) {
						$item->quantity = 0;
					}
					if ($item->sku && isset($stockChanges[$item->sku])) {
						// apply stock changes from all stock enablement periods
						$item->quantity -= $stockChanges[$item->sku];
						if ($item->quantity < 0) $item->quantity = 0;
					}
					// true if stock management is CURRENTLY enabled for this item
					$item->stockManaged = $stockSettings->enableManagement && $item->sku;
					$item->maxQuantity = $item->quantity;

					if (!isset($item->customFields) || !is_array($item->customFields)) {
						$item->customFields = array();
					}

					$item->hasVariants = false;
					if (!isset($item->variants) || !is_array($item->variants)) {
						$item->variants = array();
					}
					$minVariantFullPrice = 0;
					$minVariantPrice = 0;
					$maxVariantPrice = -1;
					$maxVariantQuantity = 0;
					foreach ($item->variants as $v) {
						if (!isset($v->price) || !is_numeric($v->price) || $v->price <= 0) {
							$v->price = 0;
						}
						if (!isset($v->discount) || !is_numeric($v->discount) || $v->discount < 0) {
							$v->discount = 0;
						} else if ($v->discount > 100) {
							$v->discount = 100;
						}
						$isEnabled = $v->price > 0;
						list($vDiscountedPrice) = self::applyPriceDiscount($item, $v, $v->price);
						if ($isEnabled && ($minVariantPrice == 0 || $minVariantPrice > $vDiscountedPrice)) {
							$minVariantFullPrice = $v->price;
							$minVariantPrice = $vDiscountedPrice;
						}
						if ($isEnabled && $maxVariantPrice < $vDiscountedPrice) {
							$maxVariantPrice = $vDiscountedPrice;
						}
						if (!isset($v->quantity) || !is_numeric($v->quantity) || $v->quantity <= 0) {
							$v->quantity = 0;
						}
						if (!isset($v->sku) || !is_string($v->sku) || !$v->sku) {
							$v->sku = '';
						}
						if ($isEnabled) $item->hasVariants = true;

						if ($v->sku && isset($stockChanges[$v->sku])) {
							// apply stock changes from all stock enablement periods
							$v->quantity -= $stockChanges[$v->sku];
							if ($v->quantity < 0) $v->quantity = 0;
						}
						if ($isEnabled && $maxVariantQuantity < $v->quantity) {
							// count quantity for enabled variants only
							$maxVariantQuantity = $v->quantity;
						}
					}
					if ($item->hasVariants) {
						$item->minFullPrice = $minVariantFullPrice;
						$item->minPrice = $minVariantPrice;
						$item->maxPrice = $maxVariantPrice;
						$item->maxQuantity = $maxVariantQuantity;
						if ($stockSettings->enableManagement) {
							$item->stockManaged = true;
						}
					}
					$defaultTaxRate = 1 + self::getDefaultTaxRateWithIncluded($item->itemType);
					$item->minFullPrice *= $defaultTaxRate;
					$item->minPrice *= $defaultTaxRate;
				}
				$data->itemStockChangesApplied = true;
			}
			return $data->items;
		}
		return array();
	}
	
	/**
	 * @param int $id
	 * @return \Profis\SitePro\controller\StoreDataItem|null
	 */
	public static function findItemById($id) {
		if (!self::$itemIdx) {
			self::$itemIdx = array();
			foreach (self::getItems() as $item) {
				self::$itemIdx[(string) $item->id] = $item;
			}
		}

		return ($id && isset(self::$itemIdx[(string) $id]))
			? self::$itemIdx[(string) $id]
			: null;
	}

	/**
	 * @param string[]|object $image
	 * @return bool
	 */
	public static function hasAnyImageResolution($image) {
		foreach ($image as $uri) {
			if ($uri) return true;
		}
		return false;
	}

	/**
	 * @param string[]|object $image
	 * @return ?string
	 */
	public static function getAnyImageResolution($image) {
		foreach ($image as $uri) {
			if ($uri) return $uri;
		}
		return null;
	}

	/**
	 * @param StoreNavigation $request
	 * @param StoreDataItem[] $items
	 * @param $imageResolution
	 * @return array
	 */
	public static function serializeItemsForJs(StoreNavigation $request, $items, $imageResolution = null) {
		$currency = StoreData::getCurrency();
		$priceOptions = StoreData::getPriceOptions();
		$result = array();

		$urlAnchor = StoreModule::$storeAnchor ? '#'.StoreModule::$storeAnchor : '';

		foreach ($items as $item) {
			$variant = StoreData::detectItemVariant($item, $item);
			$name = $variant ? StoreData::buildVariantName($variant, $item->name) : $item->name;
			$obj = (object) array(
				'id' => $item->id,
				'hasVariants' => $item->hasVariants,
				'url' => htmlspecialchars($request->detailsUrl($item).$urlAnchor),
				'name' => tr_($name),
				'description' => tr_($item->description),
				'price' => null,
				'minFullPrice' => null,
				'minDiscount' => null,
				'sku' => $item->sku,
			);

			if ($item->minPrice) {
				$obj->price = StoreData::formatPrice($item->minPrice, $priceOptions, $currency);
				if ($item->minPrice != $item->minFullPrice) {
					$obj->minFullPrice = StoreData::formatPrice($item->minFullPrice, $priceOptions, $currency);
				}
				if (isset($showDiscountLabel) && $showDiscountLabel && $item->minDiscount > 0) {
					$obj->minDiscount = "-{$item->minDiscount}%";
				}
			} else {
				$obj->price = '-';
			}

			if ($imageResolution) {
				$obj->image = isset($item->image->image->{$imageResolution})
					? $item->image->image->{$imageResolution}
					: null;
			} else {
				$obj->image = StoreData::getAnyImageResolution($item->image->image);
			}

			if (!$item->stockManaged || $item->maxQuantity > 0) {
				$result[] = $obj;
			}
		}

		return $result;
	}

	/**
	 * @param \Profis\SitePro\controller\StoreDataItem $item
	 * @param string $id
	 * @return \Profis\SitePro\controller\StoreDataItemVariant|null
	 */
	public static function findItemVariantById($item, $id) {
		foreach ($item->variants as $v) {
			if ($v->id == $id) return $v;
		}
		return null;
	}

	/**
	 * @param \Profis\SitePro\controller\StoreDataItem $item
	 * @param \Profis\SitePro\controller\StoreDataItemVariant|null $variant
	 * @param float $price
	 * @return float[]
	 */
	public static function applyPriceDiscount($item, $variant, $price) {
		$discount = 0;
		if ($variant && $variant->discount > 0 && $variant->discount <= 100) {
			$discount = $variant->discount;
		} else if ($item->discount > 0 && $item->discount <= 100) {
			$discount = $item->discount;
		}
		if ($discount > 0) {
			return array($price * (100 - $discount) / 100, $discount);
		} else {
			return array($price, 0);
		}
	}

	/**
	 * @param \Profis\SitePro\controller\StoreDataItem $item
	 * @param \Profis\SitePro\controller\StoreDataItemVariant $variant
	 * @return string cart item ID
	 */
	public static function applyItemVariant($item, $variant) {
		$item->price = $variant->price;
		if ($variant->discount > 0 && $variant->discount <= 100) {
			$item->discount = $variant->discount;
		}
		$item->quantity = $variant->quantity;
		$item->sku = $variant->sku;
		if (isset($variant->image) && $variant->image) {
			$item->image = $variant->image;
		}

		return $item->id.'_'.$variant->id;
	}

	/**
	 * @param \Profis\SitePro\controller\StoreDataItem $item
	 * @param \Profis\SitePro\controller\StoreDataItem $cartItem
	 * @return \Profis\SitePro\controller\StoreDataItemVariant|null
	 */
	public static function detectItemVariant($item, $cartItem) {
		if ($item->hasVariants
				&& (string)$item->id != $cartItem->cartId
				&& strpos($cartItem->cartId, '_') !== false) {
			list(, $variantId) = explode('_', $cartItem->cartId, 2);
			if ($variantId) {
				return StoreData::findItemVariantById($item, $variantId);
			}
		}
		return null;
	}

	/** @return object */
	public static function initVariantComponentFilter() {
		return (object) array('fields' => array(), 'items' => array());
	}

	/**
	 * @param object $filter
	 * @param int $fieldTypeId
	 * @param int $optionId
	 * @return void
	 */
	public static function addVariantComponentFilter($filter, $fieldTypeId, $optionIds) {
		foreach ($optionIds as $id) {
			$filter->fields[(string) $fieldTypeId] = intval($fieldTypeId);
			$filter->items[] = $fieldTypeId.':'.$id;
		}
	}

	/**
	 * @param \Profis\SitePro\controller\StoreDataItem $item
	 * @param object $filter
	 * @return int[]
	 */
	public static function getItemVariantComponents($item, $filter) {
		$result = array();
		$filterSize = count($filter->fields);
		foreach ($item->variants as $variant) {
			$fieldIdPairs = explode('_', $variant->id);
			if ($filterSize > 0 && count(array_intersect($fieldIdPairs, $filter->items)) != $filterSize) {
				continue;
			}
			foreach ($fieldIdPairs as $fieldIdPair) {
				if (strpos($fieldIdPair, ':') === false) continue;
				list($fieldTypeId, $optId) = explode(':', $fieldIdPair, 2);
				if (!isset($result[$fieldTypeId])) $result[$fieldTypeId] = array();
				$result[$fieldTypeId][$optId] = intval($optId);
			}
		}
		foreach ($result as $k => $v) $result[$k] = array_values($v);
		return $result;
	}

	/**
	 * @param \Profis\SitePro\controller\StoreDataItemVariant $variant
	 * @param string $baseName
	 * @return string variant name
	 */
	public static function buildVariantName($variant, $baseName = '') {
		$name = array();
		$langs = trLangs_($baseName);
		foreach (explode('_', $variant->id) as $fieldIdPair) {
			if (strpos($fieldIdPair, ':') === false) continue;
			list($fieldTypeId, $optId) = explode(':', $fieldIdPair, 2);
			$fieldType = self::getItemFieldType($fieldTypeId);
			$nameSection = $fieldIdPair;
			if ($fieldType) {
				foreach ($fieldType->options as $opt) {
					if ($opt->id == $optId) {
						$nameSection = $opt->name;
						$langs = array_merge($langs, trLangs_($opt->name));
						break;
					}
				}
			}
			$name[] = $nameSection;
		}

		// Build name for all translations
		if (empty($langs)) $langs[] = 'default';
		$result = (object) array();
		foreach ($langs as $ln) {
			$name0 = tr_($baseName, $ln);
			$name1 = implode(' / ', array_map(function($v) use ($ln) { return tr_($v, $ln); }, $name));
			$result->{$ln} = ($name0 ?: "")
				.($name1 ? ($name0 ? " ({$name1})" : $name1) : "");
		}

		return isset($result->default) ? $result->default : $result;
	}

	/** @return \Profis\SitePro\controller\StoreDataItemType[] */
	public static function getItemTypes() {
		if (($data = self::getData()) && isset($data->itemTypes) && is_array($data->itemTypes)) {
			return $data->itemTypes;
		}
		return array();
	}
	
	/** @return \Profis\SitePro\controller\StoreDataItemFieldType[] */
	public static function getItemFieldTypes() {
		if (($data = self::getData()) && isset($data->itemFieldTypes) && is_array($data->itemFieldTypes)) {
			return $data->itemFieldTypes;
		}
		return array();
	}
	
	/**
	 * @param string $id
	 * @return \Profis\SitePro\controller\StoreDataCategory
	 */
	public static function getCategory($id) {
		if (!self::$categoryIdx) {
			self::$categoryIdx = array();
			$list = self::getCategories();
			for ($i = 0, $c = count($list); $i < $c; $i++) {
				self::$categoryIdx[$list[$i]->id] = $list[$i];
			}
		}
		return ($id && isset(self::$categoryIdx[$id])) ? self::$categoryIdx[$id] : null;
	}
	
	/**
	 * @param string
	 * @return \Profis\SitePro\controller\StoreDataItemType
	 */
	public static function getItemType($id) {
		if (!self::$itemTypeIdx) {
			self::$itemTypeIdx = array();
			$list = self::getItemTypes();
			for ($i = 0, $c = count($list); $i < $c; $i++) {
				self::$itemTypeIdx[$list[$i]->id] = $list[$i];
			}
		}
		return ($id && isset(self::$itemTypeIdx[$id])) ? self::$itemTypeIdx[$id] : null;
	}
	
	/**
	 * @param \Profis\SitePro\controller\StoreDataItemType $itemType
	 * @param int $id
	 * @return \Profis\SitePro\controller\StoreDataItemTypeField
	 */
	public static function getItemTypeField($itemType, $id) {
		if (!$itemType) return null;
		if (!isset($itemType->fieldsIdx)) {
			$itemType->fieldsIdx = array();
			for ($i = 0, $c = count($itemType->fields); $i < $c; $i++) {
				$itemType->fieldsIdx[$itemType->fields[$i]->id] = $itemType->fields[$i];
			}
		}
		return ($id && isset($itemType->fieldsIdx[$id])) ? $itemType->fieldsIdx[$id] : null;
	}
	
	/** @return \Profis\SitePro\controller\StoreDataItemFieldType */
	public static function getItemFieldType($id) {
		if (!self::$itemFieldTypeIdx) {
			self::$itemFieldTypeIdx = array();
			$list = self::getItemFieldTypes();
			for ($i = 0, $c = count($list); $i < $c; $i++) {
				self::$itemFieldTypeIdx[$list[$i]->id] = $list[$i];
			}
		}
		return ($id && isset(self::$itemFieldTypeIdx[$id])) ? self::$itemFieldTypeIdx[$id] : null;
	}

	/** @return \Profis\SitePro\controller\StoreStockSettings|null */
	public static function getStockSettings() {
		return ($data = self::getData()) ? $data->stockSettings : null;
	}

	/** @return \Profis\SitePro\controller\StoreDefaultTaxSettings|null */
	public static function getDefaultTaxSettings() {
		return ($data = self::getData()) ? $data->defaultTax : null;
	}

	/**
	 * @param string $key
	 * @return object|null
	 */
	public static function findApiKeyByKey($key) {
		$data = self::getData();
		if ($data && isset($data->apiKeys) && is_array($data->apiKeys)) {
			foreach ($data->apiKeys as $apiKey) {
				if ($apiKey->key == $key) return $apiKey;
			}
		}
		return null;
	}

	/** @return string|string[]|null */
	public static function getCompanyInfo() {
		if (($data = self::getData()) && !empty($data->companyInfo)) {
			return $data->companyInfo;
		}
		return null;
	}

	/** @return string|string[]|null */
	public static function getInvoiceTitlePhrase() {
		if (($data = self::getData()) && isset($data->invoiceTitlePhrase) && !empty($data->invoiceTitlePhrase)) {
			return $data->invoiceTitlePhrase;
		}
		return StoreModule::__('Invoice');
	}

	/** @return string|null */
	public static function getInvoiceLogo() {
		if (($data = self::getData()) && isset($data->invoiceLogo) && !empty($data->invoiceLogo)) {
			return $data->invoiceLogo;
		}
		return null;
	}

	/** @return string|null */
	public static function getSignImage() {
		if (($data = self::getData()) && isset($data->signImage) && !empty($data->signImage)) {
			return $data->signImage;
		}
		return null;
	}

	/** @return string|null */
	public static function getSignImageAlign() {
		if (($data = self::getData()) && isset($data->signImageAlign) && !empty($data->signImageAlign)) {
			return $data->signImageAlign;
		}
		return null;
	}
	
	/** @return string|null */
	public static function getLogoAlign() {
		if (($data = self::getData()) && isset($data->logoAlign) && !empty($data->logoAlign)) {
			return $data->logoAlign;
		}
		return null;
	}

	/** @return string|null */
	public static function getLogoHeight() {
		if (($data = self::getData()) && isset($data->logoHeight) && !empty($data->logoHeight)) {
			return $data->logoHeight;
		}
		return null;
	}

	public static function getInvoiceON() {
		if (($data = self::getData()) && isset($data->invoiceON)) {
			return $data->invoiceON;
		}
		return true;
	}

	/** @return string|null */
	public static function getSignImageHeight() {
		if (($data = self::getData()) && isset($data->signatureHeight) && !empty($data->signatureHeight)) {
			return $data->signatureHeight;
		}
		return null;
	}

	/**
	 * @param string|null $dateTime
	 * @return array|string|string[]|null
	 */
	public static function getFormattedDate($dateTime = null) {
		if (($data = self::getData()) && isset($data->dateFormat) && !empty($data->dateFormat)) {
			$dateTime = new DateTime($dateTime ?: 'now');
			$dt = $data->dateFormat;
			$dt = str_replace("{YYYY}", $dateTime->format("Y"), $dt);
			$dt = str_replace("{YY}", $dateTime->format("y"), $dt);
			$dt = str_replace("{MM}", $dateTime->format("m"), $dt);
			$dt = str_replace("{M}", $dateTime->format("n"), $dt);
			$dt = str_replace("{DD}", $dateTime->format("d"), $dt);
			$dt = str_replace("{D}", $dateTime->format("j"), $dt);
			return StoreInvoice::fontize($dt);
		}
		return null;
	}

	/** @return string|string[]|null */
	public static function getInvoiceTextBeginning() {
		if (($data = self::getData()) && isset($data->invoiceTextBeginning) && !empty($data->invoiceTextBeginning)) {
			return $data->invoiceTextBeginning;
		}
		return null;
	}
	
	/** @return string|string[]|null */
	public static function getInvoiceTextEnding() {
		if (($data = self::getData()) && isset($data->invoiceTextEnding) && !empty($data->invoiceTextEnding)) {
			return $data->invoiceTextEnding;
		}
		return null;
	}

	/** @return string|null */
	public static function getInvoiceDocumentNumberFormat() {
		if (($data = self::getData()) && !empty($data->invoiceDocumentNumberFormat)) {
			return $data->invoiceDocumentNumberFormat;
		}
		return null;
	}

	/** @return bool */
	public static function getTermsCheckboxEnabled() {
		if (($data = self::getData()) && property_exists($data, 'termsCheckboxEnabled')) {
			return !!$data->termsCheckboxEnabled;
		}
		return false;
	}

	/** @return string|string[]|null */
	public static function getTermsCheckboxText() {
		if (($data = self::getData()) && !empty($data->termsCheckboxText)) {
			return $data->termsCheckboxText;
		}
		return null;
	}

	/** @return float */
	public static function getMinOrderPrice() {
		if (($data = self::getData()) && !empty($data->minOrderPrice)) {
			return $data->minOrderPrice;
		}
		return 0;
	}
	
	/**
	 * @param int $categoryId
	 * @return Profis\SitePro\controller\StoreDataCategory[]
	 */
	public static function getCategoryItems($categoryId) {
		$catItems = array();
		$items = self::getItems();
		foreach ($items as $item) {
			if (in_array($categoryId, $item->categories)) {
				$catItems[] = $item;
			}
		}
		return $catItems;
	}
	
	/**
	 * Checks if category contains item.
	 * @param int $categoryId
	 * @param int $itemId
	 * @return bool
	 */
	public static function categoryHasItem($categoryId, $itemId) {
		$categories = self::getCategories();
		foreach ($categories as $category) {
			if ($category->id == $categoryId) {
				$items = self::getCategoryItems($categoryId);
				foreach ($items as $item) {
					if ($item->id == $itemId) {
						return true;
					}
				}
			}
		}
		return false;
	}

	/** @return WB_FormData|null */
	public static function getBillingForm() {
		if (($data = self::getData())) {
			return (object)array(
				'class' => 'Form',
				'width' => '100%',
				'content' => (object)array_merge((array)$data->configForm, ['fields' => $data->billingFields])
			);
		}
		return null;
	}

	/** @return WB_FormData|null */
	public static function getContactForm() {
		if (($data = self::getData())) {
			return (object)array(
				'class' => 'Form',
				'width' => '100%',
				'content' => (object)array_merge((array)$data->configForm, ['fields' => $data->contactFields])
			);
		}
		return null;
	}

	public static function generateGoogleFeed()
	{
		$items = self::getItems();
		$currency = self::getCurrency();
		$stockSettings = StoreData::getStockSettings();

		$xml = new \DOMDocument('1.0', 'UTF-8');
		$rss = $xml->createElement('rss');
		$rss->setAttribute('xmlns:g', 'http://base.google.com/ns/1.0');
		$rss->setAttribute('version', '2.0');

		$channel = $xml->createElement('channel');
		$title = $xml->createElement('title', StoreModule::$siteInfo->prettyDomain);
		$link = $xml->createElement('link', getBaseUrl());
		$description = $xml->createElement('description', 'Products data feed for google.');

		$channel->appendChild($title);
		$channel->appendChild($link);
		$channel->appendChild($description);

		foreach ($items as $item) {
			$Item = $xml->createElement('item');
			if ($item->id) {
				$Item->appendChild($xml->createElement('g:id', $item->id));
			}
			if ($item->name) {
				$Item->appendChild($xml->createElement('g:title', $item->name));
			}
			if ($item->description) {
				$Item->appendChild($xml->createElement('g:description', html_entity_decode(strip_tags($item->description))));
			}
			if ($item->price) {
				$Item->appendChild($xml->createElement('g:price', number_format($item->price, 2) . ' ' . $currency->code));
			}

			$stock = !empty($stockSettings->enableManagement) ? ($item->quantity ? 'in_stock' : 'out_of_stock') : 'in_stock';
			$Item->appendChild($xml->createElement('g:availability', $stock));

			if ($item->alias) {
				$Item->appendChild($xml->createElement('g:link', getBaseUrl() . $item->alias));
			}
			if (isset($item->image)) {
				$Item->appendChild($xml->createElement('g:image_link', getBaseUrl() . $item->image->src));
			}

			$channel->appendChild($Item);
		}

		$rss->appendChild($channel);
		$xml->appendChild($rss);

		return $xml->saveXML();
	}

	public static function generateFacebookFeed()
	{
		$items = self::getItems();
		$currency = self::getCurrency();
		$stockSettings = StoreData::getStockSettings();

		$xml = new \DOMDocument('1.0', 'UTF-8');
		$rss = $xml->createElement('rss');
		$rss->setAttribute('xmlns:g', 'http://base.google.com/ns/1.0');
		$rss->setAttribute('version', '2.0');

		$channel = $xml->createElement('channel');
		$title = $xml->createElement('title', StoreModule::$siteInfo->prettyDomain);
		$link = $xml->createElement('link', getBaseUrl());
		$description = $xml->createElement('description', 'Products data feed for facebook.');

		$channel->appendChild($title);
		$channel->appendChild($link);
		$channel->appendChild($description);

		foreach ($items as $item) {
			$Item = $xml->createElement('item');
			if ($item->id) {
				$Item->appendChild($xml->createElement('g:id', $item->id));
			}
			if ($item->name) {
				$Item->appendChild($xml->createElement('g:title', $item->name));
			}
			if ($item->description) {
				$Item->appendChild($xml->createElement('g:description', html_entity_decode(strip_tags($item->description))));
				$frag = $xml->createDocumentFragment();
				$frag->appendXML(htmlspecialchars_decode($item->description));
				$rich = $xml->createElement('g:rich_text_description');
				$rich->appendChild($frag);
				$Item->appendChild($rich);
			}

			$stock = !empty($stockSettings->enableManagement) ? ($item->quantity ? 'in stock' : 'out of stock') : 'in stock';
			$Item->appendChild($xml->createElement('g:availability', $stock));

			$Item->appendChild($xml->createElement('g:condition', 'new'));
			$Item->appendChild($xml->createElement('g:brand', $item->sku ? $item->sku : 'undefined'));

			if ($item->price) {
				$Item->appendChild($xml->createElement('g:price', number_format($item->price, 2) . ' ' . $currency->code));
			}

			if ($item->alias) {
				$Item->appendChild($xml->createElement('g:link', getBaseUrl() . $item->alias));
			}

			if ($item->image) {
				$Item->appendChild($xml->createElement('g:image_link', getBaseUrl() . $item->image->src));
			}

			$channel->appendChild($Item);
		}

		$rss->appendChild($channel);
		$xml->appendChild($rss);

		return $xml->saveXML();
	}

	public static function generateYandexFeed()
	{
		date_default_timezone_set('UTC');

		$categoriesList = self::getCategories();
		$items = self::getItems();
		$currencyInfo = self::getCurrency();

		$xml = new \DOMDocument('1.0', 'UTF-8');
		$yml = $xml->createElement('yml_catalog');

		$yml->setAttribute('date', date('Y-m-d\TH:i:s+00:00'));

		$shop = $xml->createElement('shop');

		$name = $xml->createElement('name', StoreModule::$siteInfo->prettyDomain);
		$company = $xml->createElement('company', StoreModule::$siteInfo->prettyDomain);
		$url = $xml->createElement('url', getBaseUrl());

		$currencies = $xml->createElement('currencies');
		$currency = $xml->createElement('currency');
		$currency->setAttribute('id', $currencyInfo->code);
		$currency->setAttribute('rate', '1');

		$currencies->appendChild($currency);

		$categories = $xml->createElement('categories');

		$hashCategories = [];
		foreach ($categoriesList as $category) {
			$hCat = substr(base_convert(md5($category->id), 16, 10), 0, 18);
			$hashCategories[$category->id] = $hCat;

			$cat = $xml->createElement('category', $category->name);
			$cat->setAttribute('id', $hCat);
			$categories->appendChild($cat);
		}

		$shop->appendChild($name);
		$shop->appendChild($company);
		$shop->appendChild($url);
		$shop->appendChild($currencies);
		$shop->appendChild($categories);

		$offers = $xml->createElement('offers');

		foreach ($items as $item) {
			$offer = $xml->createElement('offer');

			if ($item->id) {
				$offer->setAttribute('id', $item->id);
			}
			if ($item->name) {
				$offer->appendChild($xml->createElement('name', $item->name));
			}
			if ($item->alias) {
				$offer->appendChild($xml->createElement('url', getBaseUrl() . $item->alias));
			}
			if ($item->price) {
				$offer->appendChild($xml->createElement('price', number_format($item->price, 2, '.', '')));
			}
			$offer->appendChild($xml->createElement('currencyId', $currencyInfo->code));
			if (count($item->categories) && isset($hashCategories[$item->categories[0]])) {
				$offer->appendChild($xml->createElement('categoryId', $hashCategories[$item->categories[0]]));
			}

			$offers->appendChild($offer);
		}

		$shop->appendChild($offers);

		$yml->appendChild($shop);
		$xml->appendChild($yml);

		return $xml->saveXML();
	}
}
