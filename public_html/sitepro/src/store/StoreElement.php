<?php

/**
 * @property StoreElementOptions $options
 */
class StoreElement extends StoreBaseElement {
	
	private static $cartRendered = array();
	
	private static function getSortingFuncList() {
		return array(
			'none' => (object) array(
				'name' => StoreModule::__('None'),
				'method' => null
			),
			'priceLowHigh' => (object) array(
				'name' => StoreModule::__('Price (low to high)'),
				'method' => 'itemSorterByPriceLowHigh'
			),
			'priceHighLow' => (object) array(
				'name' => StoreModule::__('Price (high to low)'),
				'method' => 'itemSorterByPriceHighLow'
			),
			'dateNewOld' => (object) array(
				'name' => StoreModule::__('Date') . ' (' . StoreModule::__('newest first') . ')',
				'method' => 'itemSorterByDateNewOld'
			)
		);
	}
	
	public function __construct($options) {
		parent::__construct($options);
	}
	
	private function renderCartAction(StoreNavigation $request) {
		$storeItems = StoreData::getItems();
		$cartData = StoreData::getCartData();
		$items = $cartData->items;
		$imageResolution = $this->options->imageWidth . 'x' . $this->options->imageHeight;
		$modified = false;
		$res = new StoreCartTotals();
		StoreCartApi::calcTaxesAndShipping($res, $cartData, $modified, true);

		$availableCodes = StoreData::getAvailableShippingCountryAndRegionCodes();
		if( empty($availableCodes) )
			$availableCodes = new stdClass(); // force to be serialized to JSON as object

		$termsCheckboxText = null;
		if( StoreData::getTermsCheckboxEnabled() ) {
			$text = StoreData::getTermsCheckboxText();
			if( !empty($text) ) {
				if( is_object($text) || is_array($text) ) {
					$text = (array)$text;
					if( !empty($text[$request->lang]) ) {
						$termsCheckboxText = $text[$request->lang];
					}
					else if( !empty($text[$request->defLang]) ) {
						$termsCheckboxText = $text[$request->defLang];
					}
					else {
						foreach( $text as $tocLn => $tocText ) {
							if( !empty($tocText) ) {
								$termsCheckboxText = $tocText;
								break;
							}
						}
					}
				}
				else
					$termsCheckboxText = $text;
			}
		}

		$urlAnchor = StoreModule::$storeAnchor ? '#'.StoreModule::$storeAnchor : '';

		$itemUrls = [];
		$linkProductsIds = [];
		foreach ($items as $item) {
			$itemUrls[$item->id] = htmlspecialchars($request->detailsUrl($item, null, null, true)) . $urlAnchor;
			if (isset($item->linkProducts) && is_array($item->linkProducts)) {
				$linkProductsIds[] = $item->linkProducts;
			}
		}

		$linkProductsIds = array_merge([], ...$linkProductsIds);
		$linkProducts = [];
		foreach ($storeItems as $storeItem) {
			if (!$storeItem->isHidden && !isset($itemUrls[$storeItem->id]) && in_array($storeItem->id, $linkProductsIds)) {
				$linkProducts[] = $storeItem;
			}
		}

		$billingFields = isset($this->options->billingFields) ? $this->options->billingFields : [];
		foreach ($billingFields as &$field) {
			$field->name = $this->__htmlToText(trim($this->__tr(isset($field->name) ? $field->name : '')));
			if (isset($field->settings->options) && is_array($field->settings->options)) {
				foreach ($field->settings->options as &$fieldOption) {
					$fieldOption = $this->__tr($fieldOption);
				}
			}
		}

		$this->renderView($this->viewPath.'/cart.php', array(
			'elementId' => $this->options->id,
			'items' => $items,
			'itemsUrl' => $itemUrls,
			'storeData' => array(
				'billingFields' => $billingFields,
				'currency' => StoreData::getCurrency(),
				'priceOptions' => StoreData::getPriceOptions(),
				'minOrderPrice' => StoreData::getMinOrderPrice(),
				'items' => $cartData->serializeItemsForJs($imageResolution),
				'linkProducts' => StoreData::serializeItemsForJs($request, $linkProducts, $imageResolution),
				'billingInfo' => ($cartData->billingInfo ? $cartData->billingInfo : new StoreBillingInfo()),
				'deliveryInfo' => ($cartData->deliveryInfo ? $cartData->deliveryInfo : new StoreBillingInfo()),
				'billingShippingRequired' => StoreData::getBillingShippingRequired(),
				'deliveryInfoRequired' => StoreData::getDeliveryInfoRequired(),
				'hasCoupons' => count(StoreData::getCoupons()) > 0,
				'coupon' => $cartData->serializeCouponForJs(),
				'discountPrice' => $res->discountPrice,
				'orderComment' => $cartData->orderComment,
				'checkoutUrl' => $request->getUri('store-submit/__GATEWAY_ID__'),
				'backUrl' => self::applyAnchor($request->detailsUrl(null), $this->options),
				'countries' => StoreCountry::buildList(),
				'shippingRegionCodes' => $availableCodes,
				'termsCheckboxEnabled' => StoreData::getTermsCheckboxEnabled(),
				'lang' => $request->getCurrLang(),
				'translations' => array(
					'You must agree to terms and conditions' => StoreModule::__('You must agree to terms and conditions'),
					'Apply' => StoreModule::__('Apply'),
					'Remove' => StoreModule::__('Remove'),
					'Tax' => StoreModule::__('Tax'),
					'Shipping Tax' => StoreModule::__('Shipping Tax'),
					'Order with obligation to pay' => StoreModule::__('Order with obligation to pay'),
					'Add to cart' => StoreModule::__('Add to cart'),
					'Added!' => StoreModule::__('Added!'),
				)
			),
			'hasPaymentGateways' => $this->options->hasPaymentGateways,
			'hasPaymentGatewaysFile' => ($this->options->hasPaymentGateways ? $this->getTemplateLnFile($request, 'gateways') : null),
			'hasPaymentGatewaysParams' => array(
				'currLang' => $request->getCurrLang(),
				'payPrice' => "{price}",
				'payTransactionId' => '{transactionId}',
				'payCallbackUrl' => $request->getUrl('store-callback/__GATEWAY_ID__'),
				'payReturnUrl' => $request->getUrl('store-return/__GATEWAY_ID__'),
				'payCancelUrl' => $request->getUrl('store-cancel/__GATEWAY_ID__').'?txnId=__TRANSACTION_ID__',
			),
			'hasForm' => $this->options->hasForm,
			'hasFormFile' => ($this->options->hasForm ? $this->getTemplateLnFile($request, 'form_' . $this->options->id) : null),

			'hasBillingForm' => $this->options->hasBillingForm,
			'hasBillingFormFile' => ($this->options->hasBillingForm ? $this->getTemplateLnFile($request, 'billing_form_' . $this->options->id) : null),

			'termsCheckboxText' => $termsCheckboxText,
			
			'cartUrl' => $request->detailsUrl(null, 'wb_cart'),
			'backUrl' => self::applyAnchor($request->detailsUrl(null), $this->options)
		));
	}
	
	private function renderListAction(StoreNavigation $request) {
		$pageQs = $request->getQueryParam(StoreElementPaging::PAGE_PROP);
		$cppQs = $request->getQueryParam(StoreElementPaging::CPP_PROP);
		$sorting = $request->getQueryParam('sort', isset($this->options->defaultSort) ? $this->options->defaultSort : null);
		$listQs = $request->getQueryParam('list');
		$paging = ($this->options->itemsPerPage > 0) ? new StoreElementPaging(
				($pageQs ? intval($pageQs) - 1 : 0),
				($cppQs ? intval($cppQs) : $this->options->itemsPerPage)
			) : null;
		if (!$listQs && $request->category && isset($request->category->viewType)) {
			$listQs = $request->category->viewType;
		}
		$tableView = ($listQs == 'table');
		
		StoreData::storeFilters($request->pageId, array(
				StoreElementPaging::PAGE_PROP => $pageQs,
				StoreElementPaging::CPP_PROP => $cppQs,
				'sort' => $sorting,
				'list' => $listQs,
				'filter' => $request->getQueryParam('filter')
			));
		$filters = ($this->options->itemsPerPage > 0) ? $this->collectFilters($request, $request->category) : array();
		$filterGroups = empty($filters) ? array() : array(array(), array());
		$filterPosition = isset($this->options->filterPosition) ? $this->options->filterPosition : 'top';
		foreach ($filters as $filter) {
			$filter->sizeClass = (isset($filter->halfSize) && $filter->halfSize) ? 'col-sm-2' : 'col-sm-4';
			if ((($filter->type == 'checkbox' || $filter->type == 'radiobox') && count($filter->options) > 2)
					|| $filter->type == 'variant') {
				$filter->sizeClass = 'col-sm-12';
				$filterGroups[1][] = $filter;
			} else {
				$filterGroups[0][] = $filter;
			}
			if( $filterPosition !== 'top' )
				$filter->sizeClass = 'col-xs-12';
		}
		$items = $this->getFilteredItems($request->category, $paging, $filters, $sorting);
		$hasPrice = false;
		foreach ($items as $item) {
			if ($item->minPrice && $this->formatPrice($item->minPrice)) {
				$hasPrice = true;
				break;
			}
		}

		$imageResolution = $this->options->imageWidth . 'x' . $this->options->imageHeight;
		$thumbResolution = $this->options->thumbWidth . 'x' . $this->options->thumbHeight;
		$thumbAutoCrop = $this->options->thumbAutoCrop;

		$entryAnim = null;
		$hoverAnim = null;
		$css = '';
		if (isset($this->options->animationEffectItems) && is_object($this->options->animationEffectItems)) {
			$anim = $this->options->animationEffectItems;
			if (isset($anim->normal) && is_object($anim->normal)) {
				$entryAnim = (object) array(
					'anim' => $anim->normal,
					'styleClass' => 'wb-anim wb-anim-entry '.self::buildAnimName($anim->normal),
					'time' => self::timeAnim($anim->normal),
					'delay' => self::timeAnimDelay($anim->normal),
				);
				$anim->normal->delay = 0;
				$css .= "#{$this->options->id} .wb-store-list .wb-store-item.wb-anim-entry-on {" . self::buildAnimCssString($anim->normal) . '}';
			}
			if (isset($anim->hover) && is_object($anim->hover)) {
				$hoverAnim = (object) array(
					'styleClass' => 'wb-anim '
						.((isset($anim->hover->loop) && $anim->hover->loop)
							? ' loop'
							: '')
						.self::buildAnimName($anim->hover),
				);
				$css .= "#{$this->options->id} .wb-store-list .wb-store-item:hover {" . self::buildAnimCssString($anim->hover) . '}';
			}
		}
		$i = 0;
		$itemsStyle = array();
		foreach ($items as $item) {
			$itemsStyle[$item->id] = [];
			$cls = '';
			if ($entryAnim) {
				$itemsStyle[$item->id]['data-wb-anim-entry-time'] = $entryAnim->time;
				$itemsStyle[$item->id]['data-wb-anim-entry-delay'] = $entryAnim->delay * $i;
				$cls .= " {$entryAnim->styleClass}";
			}
			if ($hoverAnim) {
				$cls .= " {$hoverAnim->styleClass}";
			}
			$itemsStyle[$item->id]['class'] = $cls;
			$i++;
		}

		$categories = StoreData::getCategories(true);
		$this->renderView($this->viewPath.'/list.php', array(
			'elementId' => $this->options->id,
			'imageResolution' => $imageResolution,
			'thumbResolution' => $thumbResolution,
			'thumbAutoCrop' => $thumbAutoCrop,
			'request' => $request,
			'category' => $request->category,
			'stockSettings' => StoreData::getStockSettings(),
			'items' => $items,
			'itemsStyle' => $itemsStyle,
			'css' => $css,
			'hasPrice' => $hasPrice,
			'categories' => $categories,
			'noPhotoImage' => StoreData::getNoPhotoImage(),
			'paging' => $paging,
			'filterPosition' => $filterPosition,
			'showAddToCartInList' => isset($this->options->showAddToCartInList) && $this->options->showAddToCartInList && $this->options->hasCart,
			'showBuyNowInList' => isset($this->options->showBuyNowInList) && $this->options->showBuyNowInList && $this->options->hasCart,
			'storeShowAddToCartText' => $this->options->storeShowAddToCartText,
			'storeShowBuyNowText' => $this->options->storeShowBuyNowText,
			'showDiscountLabel' => isset($this->options->showDiscountLabel) && $this->options->showDiscountLabel,
			'showPriceFrom' => isset($this->options->showPriceFrom) && $this->options->showPriceFrom,
			'filterGroups' => $filterGroups,
			'showCats' => !empty($categories) && count($categories) > 1 && (!$request->category || !$this->options->category || $request->category->id != $this->options->category),
			'tableFields' => ($tableView ? $this->collectTableFields($request->category) : null),
			'hasTableView' => (isset(StoreModule::$initData->hasTableView) && StoreModule::$initData->hasTableView),
			'showSorting' => isset($this->options->showSorting) && $this->options->showSorting,
			'showViewSwitch' => isset($this->options->showViewSwitch) && $this->options->showViewSwitch,
			'listControls' => $this->getTemplateLnFile($request, 'list-ctrls'),
			'tableView' => $tableView,
			'sorting' => $sorting,
			'sortingFuncList' => self::getSortingFuncList(),
			'urlAnchor' => self::applyAnchor('', $this->options),
			'cartUrl' => $request->detailsUrl(null, 'wb_cart'),
			'sortingUrl' => self::applyAnchor($request->detailsUrl(null, $request->category, false, array('sort' => '__SORT__'), true), $this->options),
			'thumbViewUrl' => self::applyAnchor($request->detailsUrl(null, $request->category, false, array('list' => 'thumbs'), true), $this->options),
			'tableViewUrl' => self::applyAnchor($request->detailsUrl(null, $request->category, false, array('list' => 'table'), true), $this->options),
			'serachUrl' => self::applyAnchor($request->detailsUrl(null, $request->category), $this->options),
			'currBaseUrl' => $request->detailsUrl(null),
			'currUrl' => $request->detailsUrl(null, $request->category)
		));
	}


	/**
	 * Does same as {@see getimagesize()}, but also supports SVG.
	 * This is a copy of {@see Media::getImageSizeEx()}.
	 *
	 * @param string $fullSrcPath
	 * @param array $imageInfo [optional]
	 * @return array|bool
	 */
	public static function getImageSizeEx($fullSrcPath, &$imageInfo = null) {
		if( preg_match("#\\.svg$#i", $fullSrcPath) ) {
			$size = array();
			$fp = @fopen($fullSrcPath, "rt");
			if( !$fp )
				return false;
			$firstBytes = fread($fp, 8192);
			if( preg_match("#<svg[^>]*>#isu", $firstBytes, $mtc) ) {
				if( preg_match("#width=['\"]\\s*([0-9\\.]+)\\s*['\"]#isu", $mtc[0], $mtc2) && preg_match("#height=['\"]\\s*([0-9\\.]+)\\s*['\"]#isu", $mtc[0], $mtc3) ) {
					$size[0] = floatval($mtc2[1]);
					$size[1] = floatval($mtc3[1]);
				}
				else if( preg_match("#viewBox=['\"]\\s*(-?[0-9\\.]+)\\s+(-?[0-9\\.]+)\\s+(-?[0-9\\.]+)\\s+(-?[0-9\\.]+)\\s*['\"]#isu", $mtc[0], $mtc2) ) {
					$size[0] = floatval($mtc2[3]) - floatval($mtc2[1]);
					$size[1] = floatval($mtc2[4]) - floatval($mtc2[2]);
				}
			}
			fclose($fp);
			if( isset($size[0]) ) {
				$size[2] = IMAGETYPE_UNKNOWN;
				$size[3] = 'width="' . $size[0] . '" height="' . $size[1] . '"';
				$size["mime"] = "image/svg+xml";
				$size["channels"] = 3;
				$size["bits"] = 8;
				return $size;
			}
			return false;
		}
		return @getimagesize($fullSrcPath, $imageInfo);
	}

	private function renderDetailsAction(StoreNavigation $request) {
		$item = $request->item;
		$cats = '';
		if (isset($item->categories)) {
			foreach ($item->categories as $catId) {
				$cat = StoreData::getCategory($catId);
				if ($cat) $cats .= ($cats ? ', ' : '').tr_($cat->name);
			}
		}

		$imageResolution = $this->options->imageWidth . 'x' . $this->options->imageHeight;
		$thumbResolution = $this->options->thumbWidth . 'x' . $this->options->thumbHeight;

		$noPhotoImage = StoreData::getNoPhotoImage();
		$imagesRaw = isset($item->altImages) ? $item->altImages : array();
		$images = array();
		foreach ($imagesRaw as $img) { if ($img && (isset($img->thumb) || (isset($img->type) && $img->type == 'video')))  $images[] = $img; }
		if ($item->image && (isset($item->image->thumb) || (isset($item->image->type) && $item->image->type == 'video'))) array_unshift($images, $item->image);
		
		$jsImages = array();
		foreach ($images as $img) {
			if (isset($img->type) && $img->type == 'video') {
				$jsImages[] = array('src' => $img->src, 'w' => '100%', 'h' => '100%');
			}
			else {
				$imgZoomSrc = ($img->zoom ? $img->zoom
					: (isset($img->image->$imageResolution) ? $img->image->$imageResolution
					: StoreData::getAnyImageResolution($img->image)));
				$imgSrc = (isset($img->image->$imageResolution) ? $img->image->$imageResolution
					: ($img->zoom ? $img->zoom
					: StoreData::getAnyImageResolution($img->image)));
				$imgThumbSrc = (isset($img->thumb->$thumbResolution) ? $img->thumb->$thumbResolution
					: (isset($img->image->$imageResolution) ? $img->image->$imageResolution
					: StoreData::getAnyImageResolution($img->image)));

				if ($imgZoomSrc && !preg_match('#^https?:\/\/#i', $imgZoomSrc)) {
					list($imgW, $imgH) = self::getImageSizeEx($request->basePath.'/'.$imgZoomSrc);
				} else {
					list($imgW, $imgH) = array(0, 0);
				}
				$jsImages[] = array(
					'zoom' => $imgZoomSrc,
					'src' => $imgSrc,
					'thumb' => $imgThumbSrc,
					'thumbs' => $img->thumb,
					'images' => $img->image,
					'w' => $imgW,
					'h' => $imgH,
					'title' => tr_($img->title),
					'description' => tr_($img->description),
					'link' => $img->link,
				);
			}
		}
		
		if (empty($images) && $noPhotoImage) $images[] = $noPhotoImage;
		
		$custFields = array();
		$variants = array();

		$microdataTypes = array();
		$itemType = StoreData::getItemType($item->itemType);
		if ($itemType) {
			$fieldValIdx = array();
			foreach ($item->customFields as $fieldVal) {
				$fieldValIdx[$fieldVal->fieldId] = $fieldVal;
			}
			
			foreach ($itemType->fields as $fieldData) {
				if (!$fieldData->id || $fieldData->isHidden) continue;
				$fieldType = $fieldData->type ? StoreData::getItemFieldType($fieldData->type) : null;
				if ($fieldType && $fieldType->type == 'variant') {
					$fieldType->name = $fieldData->name;
					$variants[] = (object) array(
						'id' => $fieldType->id,
						'name' => tr_($fieldType->name),
						'subType' => ((isset($fieldType->subType) && is_string($fieldType->subType))
							? $fieldType->subType
							: ''),
						'options' => array_map(
								function($opt) {
									return (object) array(
										'id' => $opt->id,
										'name' => tr_($opt->name),
										'value' => ((isset($opt->value) && is_string($opt->value))
											? $opt->value
											: ''),
										'available' => true,
									);
								},
								$fieldType->options),
					);
				} else if (isset($fieldValIdx[$fieldData->id])) {
					$fieldValue = self::stringifyFieldValue($fieldValIdx[$fieldData->id], $fieldData);
					if (is_null($fieldValue)) continue;
					$custFields[] = (object) array('name' => tr_($fieldData->name), 'value' => $fieldValue);

					// @note: only for types with one value (can't make microdata for two equal microdata key)
					if (isset($fieldType->microdataKey) && $fieldType->microdataKey) {
						$fieldTypeData = StoreData::getItemFieldType($fieldData->type);
						if ($fieldTypeData && in_array($fieldTypeData->type, ['input', 'textarea', 'radiobox', 'dropdown'])) {
							$microdataTypes[$fieldType->microdataKey] = $fieldValue;
						}
					}
				}
			}
		}

		$defaultTaxRate = 1 + StoreData::getDefaultTaxRateWithIncluded($item->itemType);
		foreach ($item->variants as $v) {
			$v->fullPriceStr = ($v->price > 0) ? $this->formatPrice($v->price * $defaultTaxRate) : '';
			if ($v->price > 0) {
				list($dPrice) = StoreData::applyPriceDiscount($item, $v, $v->price);
				$v->priceStr = $this->formatPrice($dPrice * $defaultTaxRate);
			} else {
				$v->priceStr = '';
			}
			if ($v->image) {
				$imgZoomSrc = ($v->image->zoom ? $v->image->zoom
					: (isset($v->image->image->$imageResolution) ? $v->image->image->$imageResolution
						: StoreData::getAnyImageResolution($v->image->image)));
				$imgSrc = (isset($v->image->image->$imageResolution) ? $v->image->image->$imageResolution
					: ($v->image->zoom ? $v->image->zoom
						: StoreData::getAnyImageResolution($v->image->image)));
				$imgThumbSrc = (isset($v->image->thumb->$thumbResolution) ? $v->image->thumb->$thumbResolution
					: (isset($v->image->image->$imageResolution) ? $v->image->image->$imageResolution
						: StoreData::getAnyImageResolution($v->image->image)));

				if ($imgZoomSrc && !preg_match('#^https?:\/\/#i', $imgZoomSrc)) {
					list($imgW, $imgH) = self::getImageSizeEx($request->basePath.'/'.$imgZoomSrc);
				} else {
					list($imgW, $imgH) = array(0, 0);
				}
				$v->image->zoom = $imgZoomSrc;
				$v->image->src = $imgSrc;
				$v->image->thumb = $imgThumbSrc;
				$v->image->thumbs = $v->image->thumb;
				$v->image->images = $v->image->image;
				$v->image->w = $imgW;
				$v->image->h = $imgH;
			}
		}
		
		$imageBlockWidth = max($this->options->imageWidth, min(count($images) * 126, 488) + 48) + 40 + 1;

		$filterQs = StoreData::loadFilters($request->pageId);
		$microData = self::buildMicroData(
				$item, $images, $imageResolution,
				$this->currency, $request, $microdataTypes);
		
		$this->renderView($this->viewPath.'/details.php', array(
			'elementId' => $this->options->id,
			'imageResolution' => $imageResolution,
			'thumbResolution' => $thumbResolution,
			'galleryFile' => $this->getTemplateLnFile($request, 'gallery_' . $this->options->id),
			'hasForm' => $this->options->hasForm,
			'hasFormFile' => ($this->options->hasForm ? $this->getTemplateLnFile($request, 'form_' . $this->options->id) : null),
			'hasCart' => $this->options->hasCart,
			'showDates' => StoreData::needToShowDates(),
			'showItemId' => StoreData::needToShowItemId(),
			'showDiscountLabel' => (isset($this->options->showDiscountLabel) && $this->options->showDiscountLabel),
			'stockSettings' => StoreData::getStockSettings(),
			'item' => $item,
			'cats' => $cats,
			'images' => $images,
			'imageBlockWidth' => $imageBlockWidth,
			'renderMicroData' => function() use ($microData) {
				return self::renderMicroData($microData);
			},
			'custFields' => $custFields,
			'variants' => ($item->hasVariants ? $variants : array()),
			'jsImages' => $jsImages,
			'formObject' => json_encode(array(
				'name' => '(ID: {{id}}) {{name}}'.
					'{{#sku}} ('.$this->__('SKU').': {{sku}}){{/sku}}'.
					'{{#price}} ('.$this->__('Price').': {{priceStr}}){{/price}}',
				'price' => $this->formatPrice($item->minPrice),
				'items' => array((object) array(
					'id' => $item->id,
					'name' => tr_($item->name),
					'sku' => $item->sku,
					'price' => $item->minPrice,
					'priceStr' => $this->formatPrice($item->minPrice),
					'qty' => 1
				))
			)),
			'cartUrl' => $request->detailsUrl(null, 'wb_cart'),
			'backUrl' => self::applyAnchor($request->detailsUrl(null, $request->lastSelectedCategory, false, $filterQs), $this->options),
			'tag' => (isset($this->options->tag) && $this->options->tag) ? $this->options->tag : 'p'
		));
	}

	/**
	 * @param \Profis\SitePro\controller\StoreDataItem $item
	 * @param \Profis\SitePro\controller\StoreImageData[] $images
	 * @param string $imageResolution
	 * @param \StoreCurrency $currency
	 * @param string[] $categories
	 * @param StoreNavigation $request
	 * @param string[][] $microdataTypes
	 * @return object
	 */
	private static function buildMicroData($item, $images, $imageResolution, $currency, $request, $microdataTypes) {
		$inStock = (!$item->stockManaged || $item->maxQuantity > 0);
		$url = $request->fullDetailsUrl($item, $request->category);
		$data = (object) [
			'type' => 'https://schema.org/Product',
			'entries' => (object) [
				'name' => self::staticNoPhp(tr_($item->name)),
				'description' => trim(strip_tags(self::staticNoPhp(tr_($item->description)))),
				'image' => [],
				'category' => [],
				'sku' => ($item->sku ? $item->sku : null),
				'url' => $url,
				'offers' => (object) [
					'type' => 'https://schema.org/Offer',
					'entries' => (object) [
						'url' => $url,
						'sku' => ($item->sku ? $item->sku : null),
						'priceCurrency' => ($currency ? $currency->code : null),
						'price' => (round($item->minPrice * 100) / 100),
						'availability' => 'https://schema.org/'.($inStock ? 'InStock' : 'OutOfStock'),
					],
				],
			],
		];

		foreach ((array)$microdataTypes as $microK => $microD) {
			$data->entries->$microK = implode(', ', (array)$microD);
		}
		foreach ($images as $im) {
			if (!isset($im->image->{$imageResolution})) continue;
			$data->entries->image[] = $request->fullFileUrl($im->image->{$imageResolution});
		}
		if (isset($item->categories)) {
			foreach ($item->categories as $catId) {
				$cat = StoreData::getCategory($catId);
				if ($cat) $data->entries->category[] = self::staticNoPhp(tr_($cat->name));
			}
		}
		return $data;
	}

	/**
	 * @param object $data
	 * @param string $name
	 * @return string
	 */
	private static function renderMicroData($data, $name = '', $lvl = 0) {
		$indent = str_repeat("\t", $lvl);
		$indentSub = str_repeat("\t", $lvl + 1);
		$result = $indent.'<div'
			.($name ? (' itemprop="'.htmlspecialchars($name).'"') : '')
			.' itemtype="'.htmlspecialchars($data->type).'" itemscope>'."\n";
		if (isset($data->entries)) {
			foreach ($data->entries as $entryName => $entryValueArr) {
				if (!is_array($entryValueArr)) $entryValueArr = [$entryValueArr];
				foreach ($entryValueArr as $entryValue) {
					if (is_null($entryValue)) continue;
					if (is_object($entryValue)) {
						$result .= self::renderMicroData($entryValue, $entryName, $lvl + 1);
					} else if (in_array($entryName, ['image', 'url', 'availability'])) {
						$result .= $indentSub
							.'<link itemprop="'.htmlspecialchars($entryName).'"'
								.' href="'.htmlspecialchars($entryValue).'" />'."\n";
					} else {
						$result .= $indentSub
							.'<meta itemprop="'.htmlspecialchars($entryName).'"'
								.' content="'.htmlspecialchars($entryValue).'" />'."\n";
					}
				}
			}
		}
		$result .= $indent.'</div>'."\n";
		return $result;
	}
	
	protected function tableFieldValues($tableFields, $item) {
		if (isset($item->customFields) && is_array($item->customFields)) {
			$itemType = StoreData::getItemType($item->itemType);
			$fieldValIdx = array();
			foreach ($item->customFields as $fieldVal) {
				$fieldValIdx[$fieldVal->fieldId] = $fieldVal;
			}
			if ($itemType) foreach ($itemType->fields as $fieldData) {
				if (!isset($tableFields[$fieldData->type]) || !isset($fieldValIdx[$fieldData->id])) continue;
				$tableFields[$fieldData->type]->value = self::stringifyFieldValue($fieldValIdx[$fieldData->id], $fieldData);
			}
		}
		return $tableFields;
	}
	
	/**
	 * Stringify custom field value.
	 * @param \Profis\SitePro\controller\StoreDataItemCustomFieldValue $customFieldValue custom field value descriptor.
	 * @param \Profis\SitePro\controller\StoreDataItemTypeField $fieldData custom field descriptor.
	 * @return string|null
	 */
	public static function stringifyFieldValue($customFieldValue, $fieldData) {
		if (!$customFieldValue || !$fieldData) return null;
		$fieldValue = $customFieldValue->value;
		$fieldTypeData = StoreData::getItemFieldType($fieldData->type);
		if ($fieldTypeData && is_array($fieldTypeData->options) && !empty($fieldTypeData->options)
				&& ($fieldTypeData->type == 'dropdown' || $fieldTypeData->type == 'checkbox' || $fieldTypeData->type == 'radiobox')) {
			$isValueId = StoreData::isUID($fieldValue, true);
			$fieldValueArr = $isValueId ? array($fieldValue) : $fieldValue;
			if (is_array($fieldValueArr)) {
				$fieldValueArrNew = array();
				foreach ($fieldTypeData->options as $opt) {
					foreach ($fieldValueArr as $val) {
						if ($opt->id != $val) continue;
						$fieldValueArrNew[] = tr_($opt->name);
						break;
					}
				}
				$fieldValue = implode(', ', $fieldValueArrNew);
			}
		} else {
			$rawArray = is_array($fieldValue);
			$fieldValue = tr_($fieldValue);
			// case of changing field type and not saving value
			if ($rawArray && is_object($fieldValue)) $fieldValue = tr_($fieldValue);
		}
		if (is_object($fieldValue) || is_array($fieldValue)) $fieldValue = print_r($fieldValue, true);
		$isValueId = StoreData::isUID($fieldValue, true);
		if (!$isValueId && !$fieldValue) return null;
		return $fieldValue;
	}
	
	private function collectTableFields($category = null) {
		$fields = array();
		$types = array();
		$items = StoreData::getItems();
		for ($i = 0, $c = count($items); $i < $c; $i++) {
			$item = $items[$i];
			if ($category && !in_array($category->id, $item->categories)) continue;
			$types[$item->itemType] = true;
		}
		$itemTypes = StoreData::getItemTypes();

		$itemTypesFields = [];
		foreach ($itemTypes as $itemType) {
			if (!isset($types[$itemType->id])) continue;
			foreach ($itemType->fields as $itemTypeField) {
				$fieldTypeData = StoreData::getItemFieldType($itemTypeField->type);
				if ((!$itemTypeField->isSearchable
						&& (!isset($itemTypeField->isSearchInterval) || !$itemTypeField->isSearchInterval))
					|| $itemTypeField->isHidden || !$fieldTypeData
					|| $fieldTypeData->type == 'variant') continue;
				$itemTypesFields[$itemType->id][] = $fieldTypeData->id;
			}
		}
		$commonItemFieldType = (count($itemTypesFields) > 1)
			? call_user_func_array('array_intersect', array_values($itemTypesFields))
			: reset($itemTypesFields);

		foreach ($itemTypes as $itemType) {
			if (!isset($types[$itemType->id])) continue;
			foreach ($itemType->fields as $itemTypeField) {
				$fieldTypeData = StoreData::getItemFieldType($itemTypeField->type);
				if ((!$itemTypeField->isSearchable
						&& (!isset($itemTypeField->isSearchInterval) || !$itemTypeField->isSearchInterval))
					|| $itemTypeField->isHidden || !$fieldTypeData
					|| $fieldTypeData->type == 'variant') continue;
				if (in_array($fieldTypeData->id, $commonItemFieldType, true)) {
					$field = (object)array(
						'id' => $fieldTypeData->id,
						'name' => tr_($itemTypeField->name),
						'value' => null
					);
					$fields[$fieldTypeData->id] = $field;
				}
			}
		}
		return $fields;
	}
	
	private function collectFilters(StoreNavigation $request, $category = null) {
		$filters = array();
		$halfSize = false;
		if (StoreData::needToShowItemId()) {
			$halfSize = true;
			$filters[] = (object) array(
				'id' => 'id',
				'halfSize' => $halfSize,
				'name' => $this->__('ID'),
				'value' => null,
				'interval' => false,
				'type' => null,
				'options' => null
			);
		}
		if (!isset($this->options->showTextFilter) || $this->options->showTextFilter) {
			$filters[] = (object) array(
				'id' => 'name',
				'halfSize' => $halfSize,
				'name' => $this->__('Text search'),
				'value' => null,
				'interval' => false,
				'type' => null,
				'options' => null
			);
		}
		if (isset(StoreModule::$initData->hasPrices) && StoreModule::$initData->hasPrices && (!isset($this->options->showPriceFilter) || $this->options->showPriceFilter)) {
			$filters[] = (object) array(
				'id' => 'price',
				'name' => $this->__('Price'),
				'value' => null,
				'interval' => true,
				'type' => null,
				'options' => null
			);
		}
		if (isset($this->options->showProductFilter) && $this->options->showProductFilter) {
			$this->options;
			$types = array();
			$items = StoreData::getItems();
			for ($i = 0, $c = count($items); $i < $c; $i++) {
				$item = $items[$i];
				if ($category && !in_array($category->id, $item->categories)) continue;
				$types[$item->itemType] = true;
			}
			$usedFieldTypes = array();
			$itemTypes = StoreData::getItemTypes();
			foreach ($itemTypes as $itemType) {
				if (!isset($types[$itemType->id])) continue;
				foreach ($itemType->fields as $itemTypeField) {
					if (isset($usedFieldTypes[$itemTypeField->type])) continue;
					$fieldTypeData = StoreData::getItemFieldType($itemTypeField->type);
					if ((!$itemTypeField->isSearchable
							&& (!isset($itemTypeField->isSearchInterval) || !$itemTypeField->isSearchInterval))
						|| !$fieldTypeData) continue;
					$usedFieldTypes[$itemTypeField->type] = true;
					$canBeInterval = ($itemTypeField->isSearchInterval && $fieldTypeData
						&& $fieldTypeData->type != 'dropdown' && $fieldTypeData->type != 'checkbox'
						&& $fieldTypeData->type != 'radiobox' && $fieldTypeData->type != 'variant');
					$filter = (object)array(
						'id' => $fieldTypeData->id,
						'name' => tr_($itemTypeField->name),
						'value' => null,
						'interval' => ($canBeInterval ? true : false),
						'type' => null,
						'options' => null
					);
					if ($fieldTypeData && is_array($fieldTypeData->options) && !empty($fieldTypeData->options)) {
						$filter->type = $fieldTypeData->type;
						$filter->options = $fieldTypeData->options;
					}

					$filters[] = $filter;
				}
			}
		}
		$filterQs = $request->getQueryParam('filter');
		$formData = ($filterQs && is_array($filterQs)) ? $filterQs : array();
		foreach ($filters as $filter) {
			$filter->value = (isset($formData[$filter->id]) ? $formData[$filter->id] : null);
			if ($filter->id === 'name' && !isset($formData[$filter->id])) {
				$filter->value = array('text' => '', 'desc' => 1);
			}
		}

		return $filters;
	}
	
	/**
	 * Store item sorter by price function (low to high).
	 * @param \Profis\SitePro\controller\StoreDataItem $a
	 * @param \Profis\SitePro\controller\StoreDataItem $b
	 */
	protected function itemSorterByPriceLowHigh($a, $b) {
		if ($a->minPrice == $b->minPrice) return 0;
		return ($a->minPrice < $b->minPrice) ? -1 : 1;
	}
	
	/**
	 * Store item sorter by price function (high to low).
	 * @param \Profis\SitePro\controller\StoreDataItem $a
	 * @param \Profis\SitePro\controller\StoreDataItem $b
	 */
	protected function itemSorterByPriceHighLow($a, $b) {
		if ($a->minPrice == $b->minPrice) return 0;
		return ($a->minPrice > $b->minPrice) ? -1 : 1;
	}
	
	/**
	 * Store item sorter by date function (oldest to newest).
	 * @param \Profis\SitePro\controller\StoreDataItem $a
	 * @param \Profis\SitePro\controller\StoreDataItem $b
	 */
	protected function itemSorterByDateOldNew($a, $b) {
		$av = isset($a->dateTimeModified) ? $a->dateTimeModified : null;
		$bv = isset($b->dateTimeModified) ? $b->dateTimeModified : null;
		if ($av == $bv) return 0;
		return ($av < $bv) ? -1 : 1;
	}
	
	/**
	 * Store item sorter by date function (newest to oldest).
	 * @param \Profis\SitePro\controller\StoreDataItem $a
	 * @param \Profis\SitePro\controller\StoreDataItem $b
	 */
	protected function itemSorterByDateNewOld($a, $b) {
		$av = isset($a->dateTimeModified) ? $a->dateTimeModified : null;
		$bv = isset($b->dateTimeModified) ? $b->dateTimeModified : null;
		if ($av == $bv) return 0;
		return ($av > $bv) ? -1 : 1;
	}
	
	/**
	 * Get filtered item list.
	 * @param \Profis\SitePro\controller\StoreDataCategory $category
	 * @param StoreElementPaging $paging
	 * @return \Profis\SitePro\controller\StoreDataItem[]
	 */
	protected function getFilteredItems($category = null, $paging = null, $filters = null, $sorting = null) {
		$list = array();
		$stockSettings = StoreData::getStockSettings();
		$items = StoreData::getItems();
		$hideOutOfStock = $stockSettings->enableManagement && $stockSettings->hideOutOfStock;
		$sortingFuncList = self::getSortingFuncList();
		if (isset($sortingFuncList[$sorting]) && $sortingFuncList[$sorting]->method) {
			usort($items, array($this, $sortingFuncList[$sorting]->method));
		}
		for ($i = 0, $c = count($items); $i < $c; $i++) {
			$item = $items[$i];
			if (isset($item->isHidden) && $item->isHidden) continue;
			if ($hideOutOfStock && $item->stockManaged && $item->maxQuantity <= 0) continue;
			if ($category && !in_array($category->id, $item->categories)) continue;
			$variantFilter = StoreData::initVariantComponentFilter();
			$fields = array('name' => tr_($item->name), 'price' => $item->minPrice, 'description' => tr_($item->description));
			$itemType = (isset($item->itemType) ? StoreData::getItemType($item->itemType) : null);
			if ($itemType) {
				foreach ($item->customFields as $field) {
					$fieldData = StoreData::getItemTypeField($itemType, $field->fieldId);
					if ($fieldData) $fields[$fieldData->type] = $field->value;
				}
				foreach (StoreData::getItemVariantComponents($item, $variantFilter) as $fieldTypeId => $values) {
					$fields[$fieldTypeId] = $values;
				}
			}
			$skip = false;
			if ($filters && !empty($filters)) {
				foreach ($filters as $filter) {
					if (!isset($filter->value) || $filter->value === '' || ($filter->interval && is_array($filter->value)
								&& (!isset($filter->value['from']) || $filter->value['from'] === '')
								&& (!isset($filter->value['to']) || $filter->value['to'] === '')
							)) continue;
					if ($filter->id == 'id') {
						if ($item->id != intval($filter->value)) $skip = true;
						break;
					}
					if (!isset($fields[$filter->id])) { $skip = true; break; }
					if ($filter->type == 'dropdown') {
						// hacky fix when changing field type from "Check Box" or "Radio Box" to "Dropdown Box"
						if (is_array($fields[$filter->id])) {
							$fields[$filter->id] = reset($fields[$filter->id]);
						}
						if ($fields[$filter->id] != $filter->value) {
							$skip = true;
							break;
						}
					} else if ($filter->type == 'variant' && is_array($filter->value)) {
						StoreData::addVariantComponentFilter($variantFilter, $filter->id, $filter->value);
						$itemVariantComponents = StoreData::getItemVariantComponents($item, $variantFilter);
						if (empty($itemVariantComponents)) {
							$skip = true;
							break;
						}
					} else if ($filter->type == 'checkbox' && is_array($filter->value)) {
						// hacky fix when changing field type from "Dropdown Box" to "Check Box"
						if (!is_array($fields[$filter->id]))
							$fields[$filter->id] = array($fields[$filter->id]);
						$common = array_intersect($fields[$filter->id], $filter->value);
						if (empty($common)) {
							$skip = true;
							break;
						}
					} else if ($filter->type == 'radiobox') {
						// hacky fix when changing field type from "Dropdown Box" to "Radio Box"
						if (!is_array($fields[$filter->id]))
							$fields[$filter->id] = array($fields[$filter->id]);
						if (!in_array($filter->value, $fields[$filter->id])) {
							$skip = true;
							break;
						}
					} else if ($filter->interval) {
						if (isset($filter->value['from']) && $filter->value['from'] !== '' && $filter->value['from'] > $fields[$filter->id]) {
							$skip = true;
							break;
						}
						if (isset($filter->value['to']) && $filter->value['to'] !== '' && $filter->value['to'] < $fields[$filter->id]) {
							$skip = true;
							break;
						}
					} else if ($filter->id == 'name') {
						$inDesc = isset($filter->value['desc']) ? !!$filter->value['desc'] : false;

						$data = tr_($fields[$filter->id]).($inDesc && isset($fields['description']) ? ('; '.$fields['description']) : '');
						if ($inDesc) {
							foreach ($item->customFields as $field) {
								$fieldData = StoreData::getItemTypeField($itemType, $field->fieldId);
								if ($fieldData) {
									$fieldTypeData = StoreData::getItemFieldType($fieldData->type);
									if ((!$fieldData->isSearchable
											&& (!isset($fieldData->isSearchInterval) || !$fieldData->isSearchInterval))
										|| $fieldData->isHidden || ($fieldTypeData
											&& $fieldTypeData->type == 'variant')) continue;
									$data .= '; ' . static::stringifyFieldValue($field, $fieldData);
								}
							}
							foreach ($item->variants as $variant) {
								$variantName = tr_(StoreData::buildVariantName($variant));
								$data .= '; ' . $variantName;
							}
						}
						$data = simplifyText($data);
						$sdata = simplifyText(isset($filter->value['text']) ? $filter->value['text'] : '');
						if ($sdata && (function_exists('mb_strpos') && mb_strpos($data, $sdata) === false || strpos($data, $sdata) === false)) {
							$skip = true;
							break;
						}
					} else {
						$data = simplifyText(tr_($fields[$filter->id]));
						$sdata = simplifyText($filter->value);
						if (!($data == $sdata || $sdata && (function_exists('mb_strpos') && mb_strpos($data, $sdata) !== false || strpos($data, $sdata) !== false))) {
							$skip = true;
							break;
						}
					}
				}
			}
			if ($skip) continue;
			$list[] = $item;
		}
		if ($paging) {
			$paging->update(count($list));
			return array_slice($list, $paging->pageIndex * $paging->itemsPerPage, $paging->itemsPerPage);
		} else {
			return $list;
		}
	}
	
	/** @param StoreElementOptions $options */
	public static function render(StoreNavigation $request, $options) {
		if ($options->category) {
			$request->category = StoreData::getCategory($options->category);
			$request->categoryKey = null;
		}
		
		$request->item = StoreModule::resolveItemByRequest($request, !!$request->category);
		if ($request->item && $request->category && !StoreData::categoryHasItem($request->category->id, $request->item->id)) {
			$request->item = null;
			$request->itemKey = null;
		}
		
		if (!StoreModule::$storeAnchor && self::isAnchorNavAvailable($options)) {
			StoreModule::$storeAnchor = $options->anchor;
		}
		
		$canRenderCart = false;
		if (isset($options->visibility) && is_array($options->visibility)) {
			foreach ($options->visibility as $mode => $visible) {
				if ($visible && !isset(self::$cartRendered[$mode])) {
					self::$cartRendered[$mode] = true;
					$canRenderCart = true;
				}
			}
		}
		
		$elem = new StoreElement($options);
		if ($request->isCart && $canRenderCart) {
			$elem->renderCartAction($request);
		} else if ($request->item) {
			$elem->renderDetailsAction($request);
		} else {
			$elem->renderListAction($request);
		}
	}
	
	/**
 	 * @param StoreElementOptions $options
	 * @return bool
	 */
	private static function isAnchorNavAvailable($options) {
		return isset($options->anchor) && $options->anchor
			&& (!isset($options->disableAnchorNav) || !$options->disableAnchorNav);
	}

	/**
	 * @param string $url
	 * @param StoreElementOptions $options
	 * @return string
	 */
	private static function applyAnchor($url, $options) {
		return $url.(self::isAnchorNavAvailable($options) ? ('#'.$options->anchor) : '');
	}

	/** @return bool */
	private static function isAnimValid(stdClass $val) {
		return ($val && isset($val->effect) && is_string($val->effect) && $val->effect);
	}

	protected static function timeAnimDelay(stdClass $val) {
		if (!self::isAnimValid($val)) return 0;
		return (isset($val->delay) && is_numeric($val->delay))
			? floatval($val->delay)
			: 0;
	}

	protected static function timeAnim(stdClass $val) {
		if (!self::isAnimValid($val)) return 0;
		$time = 0;
		$time += (isset($val->duration) && is_numeric($val->duration))
			? floatval($val->duration)
			: 0.6;
		if (isset($val->delay) && is_numeric($val->delay)) {
			$time += floatval($val->delay);
		}
		return $time;
	}

	protected static function buildAnimName(stdClass $val) {
		if (!self::isAnimValid($val)) return '';
		return 'wb-anim-'.$val->effect
			. ((isset($val->direction) && $val->direction) ? ('-'.$val->direction) : '');
	}

	protected static function buildAnimCss(stdClass $val, $useDelay = true) {
		if (!self::isAnimValid($val)) {
			return array('animation' => 'none');
		}
		return array(
			'animation' => self::buildAnimName($val)
				.' '.(isset($val->duration) ? $val->duration : '0.6').'s'
				.' '.(isset($val->timing) ? $val->timing : 'linear')
				. ($useDelay ? (' '.(isset($val->delay) ? $val->delay : '0').'s') : ''),
			'animation-iteration-count' => ($val->loop ? 'infinite' : 1),
		);
	}

	protected static function buildAnimCssString(stdClass $val, $useDelay = true) {
		$css = self::buildAnimCss($val, $useDelay);

		$r = '';
		foreach ($css as $key => $value) {
			$r .= $key . ': ' . $value . ';';
		}
		return $r;
	}
}

class StoreElementPaging {
	
	const PAGE_PROP = 'spage';
	const CPP_PROP = 'scpp';
	
	/** @var int */
	public $itemsPerPage;
	/** @var int */
	public $pageIndex = 0;
	/** @var int */
	public $pageCount;
	/** @var int */
	public $pagesInPager = 5;
	/** @var int */
	public $startPageIndex;
	/** @var int */
	public $endPageIndex;
	
	public function __construct($pageIndex, $itemsPerPage) {
		$this->pageIndex = intval($pageIndex);
		$this->itemsPerPage = intval($itemsPerPage);
	}
	
	public function update($itemCount) {
		$this->itemsPerPage = ($this->itemsPerPage > 0) ? $this->itemsPerPage : 20;
		$this->pageCount = ceil($itemCount / $this->itemsPerPage);
		if ($this->pageCount > 0) {
			$this->pageIndex = ($this->pageIndex >= 0 && $this->pageIndex < $this->pageCount) ? $this->pageIndex : 0;
		}
		$this->pagesInPager = ($this->pagesInPager > 1) ? $this->pagesInPager : 5;
		
		if ($this->pageCount > 0) {
			$this->startPageIndex = $this->pageIndex - floor($this->pagesInPager / 2);
			if ($this->startPageIndex < 0) $this->startPageIndex = 0;
			$this->endPageIndex = $this->startPageIndex + $this->pagesInPager - 1;
			if ($this->endPageIndex >= $this->pageCount) {
				$this->endPageIndex = $this->pageCount - 1;
				$iip = max($this->pagesInPager - ($this->endPageIndex - $this->startPageIndex), 0);
				$this->startPageIndex -= min($this->startPageIndex, $iip);
			}
		} else {
			$this->startPageIndex = $this->endPageIndex = 0;
		}
	}
	
}

/**
 * @property string $id
 * @property string $anchor
 * @property bool $disableAnchorNav
 * @property bool $hasPaymentGateways if true then show payment gateways in cart page
 * @property bool $hasForm if true then show form in details page
 * @property bool $hasBillingForm if true then show form in details page
 * @property bool $hasCart if true then show add to cart button in details
 * @property array $billingFields array of billing form fields
 * @property bool $filterPosition Position of filter. Either "top", "left" or "right".
 * @property bool $defaultSort Default sort
 * @property stdClass|null $animationEffectItems Animation config for products
 * @property bool $showAddToCartInList Visibility of "Add to cart" button on every item in product list
 * @property bool $showBuyNowInList Visibility of "Buy now" button on every item in product list
 * @property stdClass|string $storeShowAddToCartText add to cart text
 * @property stdClass|string $storeShowBuyNowText buy now text
 * @property bool $showTextFilter if true then show text search filter
 * @property bool $showPriceFilter if true then show price filter
 * @property bool $showProductFilter if true then show product filter
 * @property bool $showSorting Visibility of sorting dropdown
 * @property bool $showViewSwitch Visibility of table/list view switch
 * @property bool $showDiscountLabel Visibility of discount label
 * @property bool $fromPriceEnabled Visibility of "from" price
 * @property bool $showPriceFrom
 * @property int $thumbWidth Item image thumbnail width
 * @property int $thumbHeight Item image thumbnail height
 * @property bool $thumbAutoCrop Item image thumbnail image containment
 * @property int $imageWidth Item image width
 * @property int $imageHeight Item image height
 * @property int $itemsPerPage item count to show per page
 * @property int $category default category id
 * @property bool $visibility
 * @property string $tag
 */
class StoreElementOptions {}
