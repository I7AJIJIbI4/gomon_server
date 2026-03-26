<?php

use PHPMailer\PHPMailer\PHPMailer;

class StorePaymentApi {
	
	private static $gateway;

	protected function getBuilderRequestData(StoreNavigation $request, $actionId, $signatureFields = array()) {
		header('Access-Control-Allow-Origin: *', true); // allow cross domain requests

		$data = $request->getBodyAsJson();
		if( !$data || !is_object($data) || !isset($data->sig) ) {
			StoreModule::respondWithJson(array(
				"error" => array("code" => 1, "message" => "Bad request")
			));
		}

		$sigCheckStr = StoreModule::$siteInfo->websiteUID . "|" . $actionId;
		foreach ($signatureFields as $k)
			$sigCheckStr .= "|" . $k . "=" . $data->{$k};

		$expectedHash = md5($sigCheckStr);
		$hash = $this->publicDecrypt($data->sig);
		if( $hash !== $expectedHash ) {
			StoreModule::respondWithJson(array(
				"error" => array("code" => 2, "message" => "Bad signature")
			));
		}

		return $data;
	}

	protected function applyOrdersToStockAction(StoreNavigation $request) {
		$data = $this->getBuilderRequestData($request, 'apply-orders-to-stock', array('applyVersion'));
		if (!isset($data->applyVersion) || !is_numeric($data->applyVersion)) {
			StoreModule::respondWithJson(array(
				'error' => array('code' => 99, 'message' => 'Missing applyVersion field')
			));
		}

		list($result, $newApplyVersion) = StoreModuleOrder::indexStockChanges($data->applyVersion, true);

		StoreModule::respondWithJson(array(
			'ok' => true,
			'result' => (object) $result,
			'applyVersion' => $newApplyVersion,
		));
	}

	protected function storeLogAction(StoreNavigation $request) {
		$data = $this->getBuilderRequestData($request, 'store-log', array('state', 'dateFrom', 'dateTo', 'orderID'));

		$dateFrom = strtotime($data->dateFrom);
		$dateTo = strtotime($data->dateTo);

		$list = StoreModuleOrder::findAll(array(
			StoreModuleOrder::FILTER_TRANSACTION_ID => $data->orderID,
			StoreModuleOrder::FILTER_STATE => $data->state === 'all' ? null : $data->state,
			StoreModuleOrder::FILTER_DATE_TIME_GTE => $dateFrom ? date('Y-m-d H:i:s', $dateFrom) : null,
			StoreModuleOrder::FILTER_DATE_TIME_LTE => $dateTo ? date('Y-m-d H:i:s', $dateTo) : null,
		));
		foreach ($list as $idx => $li) {
			if (!$list[$idx]->getTransactionId()) {
				$list[$idx]->setTransactionId(StoreData::randomHash(9, true));
				$list[$idx]->save();
			}
			$list[$idx] = $li->jsonSerialize();
		}

		StoreModule::respondWithJson(array("ok" => true, "list" => $list, 'get' => $request->getQueryParams(), 'post' => $request->getFormParams()));
	}

	protected function removeOrderAction(StoreNavigation $request) {
		$data = $this->getBuilderRequestData($request, 'remove-order', array("id"));

		$order = StoreModuleOrder::findByTransactionId($data->id);
		if( $order && ($order->getState() == StoreModuleOrder::STATE_PENDING || $order->getState() == StoreModuleOrder::STATE_FAILED || $order->getState() == StoreModuleOrder::STATE_REFUNDED || $order->getState() == StoreModuleOrder::STATE_CANCELLED) )
			$order->delete();

		StoreModule::respondWithJson(array("ok" => true));
	}

	protected function resendInvoiceAction(StoreNavigation $request) {
		$data = $this->getBuilderRequestData($request, 'resend-invoice', array("id"));

		$order = StoreModuleOrder::findByTransactionId($data->id);
		if ($order && in_array($order->getState(), [StoreModuleOrder::STATE_COMPLETE, StoreModuleOrder::STATE_PAID])) {
			self::sendOrderEmails($request, $order, 'complete');
			$order->setInvoiceResended(true)->save();
			StoreModule::respondWithJson(array("ok" => true));
		}

		StoreModule::respondWithJson(array("ok" => false));
	}

	protected function setOrderStateAction(StoreNavigation $request) {
		$data = $this->getBuilderRequestData($request, 'set-order-state', array("id", "state"));

		$order = StoreModuleOrder::findByTransactionId($data->id);
		if ($order) {
			$order->setState($data->state)->save();
		}

		StoreModule::respondWithJson(array("ok" => true));
	}

	protected function storeSubmitAction(StoreNavigation $request) {
		$response = array('createFields' => null, 'deleteFields' => array(), 'updateFields' => array(), 'error' => null);
		try {
			$gatewayId = self::getGatewayIdFromRequest($request);
			$data = $request->getBodyAsJson();
			if (!$gatewayId || !is_object($data) || !$data
					|| !isset($data->formData) || !is_array($data->formData) || !$data->formData)
				throw new ErrorException(StoreModule::__('An error occurred. Please try again.'));

			$transactionId = (isset($data->transactionId) && $data->transactionId) ? $data->transactionId : StoreData::randomHash(9, true);

			ob_start();
			$currency = StoreData::getCurrency();
			$priceOptions = StoreData::getPriceOptions();
			$dp = pow(10, (isset($po->decimalPlaces) && ($po->decimalPlaces >= 0)) ? intval($po->decimalPlaces) : 2);
			$cartData = StoreData::getCartData(0);
			$totals = new StoreCartTotals(); StoreCartApi::calcTaxesAndShipping($totals, $cartData);
			$totals->coupon = $cartData->serializeCouponForJs();
			$orderPrice = (isset($data->orderPrice) && $data->orderPrice) ? $data->orderPrice : $totals->totalPrice;
			$order = StoreModuleOrder::findByTransactionId($transactionId);
			if (!$order) $order = new StoreModuleOrder();
			$items = StoreCartApi::buildCartItemList($order, $cartData);
			if (empty($items)) {
				throw new ErrorException(StoreModule::__('An error occurred. Please try again later.'));
			}
			$stockSettings = StoreData::getStockSettings();
			$billingForm = StoreData::getBillingForm();
			$billingFields = $billingForm ? $billingForm->content->fields : null;


			$defaultTax = StoreData::getDefaultTaxSettings();
			$isTaxIncluded = $defaultTax && $defaultTax->enabled && $defaultTax->taxIncluded;

			if ($isTaxIncluded && $totals->discountPercent && count($totals->taxes)) {
				$totals->discountPrice = round($totals->subTotalPrice * $totals->discountPercent * $dp / 100) / $dp;
			}

			$order->setTransactionId($transactionId)
					->setLang($request->getCurrLang())
					->setGatewayId($gatewayId)
					->setItems($items)
					->setPrice(floatval($orderPrice))
					->setBuyer(null)
					->setType('buy')
					->setState(StoreModuleOrder::STATE_PENDING)
					->setCurrency($currency)
					->setPriceOptions($priceOptions)
					->setBillingForm($billingFields)
					->setBillingInfo($cartData->billingInfo)
					->setDeliveryInfo($cartData->deliveryInfo)
					->setOrderComment($cartData->orderComment)
					->setTaxes(array_map(
							function(StoreCartTotalsTax $tax) {
								return new StoreModuleOrderTax($tax->rate, $tax->amount, $tax->shippingOnly);
							},
							$totals->taxes))
					->setShippingAmount($totals->shippingPrice)
					->setShippingDescription(is_string($totals->shippingMethod) ? $totals->shippingMethod : '')
					->setDiscountAmount($totals->discountPrice)
					->setStockManaged($stockSettings && $stockSettings->enableManagement)
					->setCoupon($totals->coupon)
					->saveAttachments()
					->setInvoiceON(StoreData::getInvoiceON())
					->save();
			self::handleStockNotifications($request, $order);
			$formData = array(); $updateFields = array();
			foreach ($data->formData as $field) {
				if ($field->isPrice) {
					$field->value = $orderPrice;
					$fd = (isset($field->fixedDecimal) && is_numeric($field->fixedDecimal) && $field->fixedDecimal >= 0) ? $field->fixedDecimal : 2;
					$mlp = (isset($field->multiplier) && is_numeric($field->multiplier) && $field->multiplier > 0) ? $field->multiplier : 1;
					$field->value = number_format(($orderPrice * $mlp), $fd, '.', '');
					$updateFields[$field->name] = $field->value;
				} else if ($field->value == '{transactionId}') {
					$field->value = $transactionId;
					$updateFields[$field->name] = $field->value;
				} else if (strpos($field->value, '{transactionId}') !== false) {
					$field->value = str_replace('{transactionId}', $transactionId, $field->value);
					$updateFields[$field->name] = str_replace('{transactionId}', $transactionId, $field->value);
				} else if ($field->value == 'Cart contents') {
					$updateFields[$field->name] = $field->value = StoreModule::__('Cart contents');
				}
				$formData[$field->name] = $field->value;
			}
			$response['updateFields'] = $updateFields;
			$response['orderData'] = array(
				"id" => $order->getId(),
				"transactionId" => $order->getTransactionId(),
				"invoiceUrl" => $order->getInvoiceDocumentNumber() ? self::getInvoiceUrl($request, $order) : null,
			);
			$gateway = self::getGateway($request);
			if ($gateway) {

				$backUrl = $request->getUri();

				$billingForm = StorePaymentApi::getBillingForm();
				if (isset($billingForm['redirectUrl'])) {
					$redirectUrl = tr_($billingForm['redirectUrl']);
					if ($redirectUrl == '{{base_url}}') {
						$backUrl = getBaseUrl();
					} else if (is_string($redirectUrl) && preg_match('#^https?://#i', $redirectUrl)) {
						$backUrl = $redirectUrl;
					} elseif (is_string($redirectUrl) && preg_match('#^wb_popup:#i', $redirectUrl)) {
						$backUrl = getBaseUrl() . '?wbPopupOpen=' . urlencode($redirectUrl);
					} else {
						$backUrl = getBaseUrl() . $redirectUrl;
					}
				}

				$response['createFields'] = $gateway->createFormFields($formData);
				$response['deleteFields'] = $gateway->deleteFormFields();
				$response['redirectUrl'] = $gateway->createRedirectUrl($formData);
				$response['instantRedirectUrl'] = $gateway->createInstantRedirectUrl($formData);
				$response['backUrl'] = $backUrl;
				$response['noSubmit'] = ($response['createFields'] === false);
				$response['error'] = $gateway->getLastError();
				if( !$gateway->isCallbackSupported() ) {
					StoreCartApi::clearStoreCart();
				}
				if ($gateway->doSendMailAfterOrderSubmit()) {
					self::sendOrderEmails($request, $order, 'pending');
				}
			}
			ob_end_clean();
		} catch (ErrorException $ex) {
			$response['error'] = $ex->getMessage();
		}
		StoreModule::respondWithJson($response);
		exit();
	}
	
	/**
	 * Verify function to verify payment from payment system
	 * @param StoreNavigation $request store request descriptor object.
	 */
	protected function storeVerifyAction(StoreNavigation $request) {
		$gateway = self::getGateway($request);
		file_put_contents(dirname(__FILE__).'/store_orders_verify.log', print_r(array(
			'time' => date('Y-m-d H:i:s'),
			'gateway' => self::getGatewayIdFromRequest($request),
			'POST' => $request->getFormParams(),
			'GET' => $request->getQueryParams()
		), true)."\n\n", FILE_APPEND);
		if ($gateway) {
			$order = ($txnId = $gateway->getTransactionId()) ? StoreModuleOrder::findByTransactionId($txnId) : null;
			$gateway->verify($order);
		}
		exit();
	}
	
	/**
	 * Callback function to complete payment from payment system
	 * @param StoreNavigation $request store request descriptor object.
	 */
	protected function storeCallbackAction(StoreNavigation $request) {
		$gateway = self::getGateway($request);
		try {
			$transactionId = $gateway ? $gateway->getTransactionId() : null;
			$transactionIdError = null;
		} catch (Exception $ex) {
			$transactionId = null;
			$transactionIdError = $ex->getMessage();
		}
		file_put_contents(dirname(__FILE__).'/store_orders.log', print_r(array(
			'time' => date('Y-m-d H:i:s'),
			'gateway' => self::getGatewayIdFromRequest($request),
			'gatewayOK' => ($gateway ? 'Yes' : 'No'),
			'gatewayTransactionId' => $transactionId,
			'gatewayTransactionIdError' => $transactionIdError,
			'POST' => empty($request->getFormParams()) ? file_get_contents('php://input') : $request->getFormParams(),
			'GET' => $request->getQueryParams()
		), true)."\n\n", FILE_APPEND);

		if ($gateway) {
			$order = StoreModuleOrder::findByTransactionId($gateway->getTransactionId());
			$orderState = $order ? $order->getState() : false;
			$clbRes = $gateway->callback($order);
			if (is_null($clbRes))
				throw new ErrorException('Error: Gateway callback method must return boolean value.');
			if ($clbRes && ($order = StoreModuleOrder::findByTransactionId($gateway->getTransactionId()))) {
				$clbSuccess = true;
				if ($orderState !== StoreModuleOrder::STATE_PAID) {
					$buyerData = $gateway->getClientInfo();

					if ($buyerData) $order->setBuyer(StoreModuleBuyer::create()->setData($buyerData));
					$order->setCompleteDateTime(date('Y-m-d H:i:s'))
							->setState(StoreModuleOrder::STATE_PAID)
							->setInvoiceResended(true)
							->save();

					self::sendOrderEmails($request, $order, 'complete');
				}
			} else {
				$clbSuccess = false;
			}
			if ($gateway->doReturnAfterCallback()) {
				if ($clbSuccess) {
					$this->storeReturnAction($request);
				} else {
					$this->storeCancelAction($request);
				}
			}
		}
		exit();
	}
	
	protected function storeReturnAction(StoreNavigation $request) {
		$gateway = self::getGateway($request);
		if ($gateway) $gateway->completeCheckout();
		if (session_id()) {
			$_SESSION['store_return'] = true;
			$_SESSION['store_cancel'] = null;
			unset($_SESSION['store_cancel']);
		}
		$backUrlDefault = $request->getUri();
		$billingForm = StorePaymentApi::getBillingForm();
		if (isset($billingForm['redirectUrl'])) {
			$redirectUrl = tr_($billingForm['redirectUrl']);
			if ($redirectUrl == '{{base_url}}') {
				$backUrlDefault = getBaseUrl();
			} else if (is_string($redirectUrl) && preg_match('#^https?://#i', $redirectUrl)) {
				$backUrlDefault = $redirectUrl;
			} elseif (is_string($redirectUrl) && preg_match('#^wb_popup:#i', $redirectUrl)) {
				$backUrlDefault = getBaseUrl() . '?wbPopupOpen=' . urlencode($redirectUrl);
			} else {
				$backUrlDefault = getBaseUrl() . $redirectUrl;
			}
		}
		$backUrl = $request->getFormParam('store_return_backUrl', $request->getQueryParam('store_return_backUrl', $backUrlDefault));
		StoreNavigation::redirect($backUrl);
		exit();
	}
	
	protected function storeCancelAction(StoreNavigation $request) {
		$gateway = self::getGateway($request);
		if ($gateway) $gateway->cancel();
		$orderId = $request->getQueryParam('txnId');
		/** @var StoreModuleOrder $order */
		$order = $orderId ? StoreModuleOrder::findByTransactionId($orderId) : null;
		if ($order && $order->getState() != StoreModuleOrder::STATE_CANCELLED) {
			$order->setState(StoreModuleOrder::STATE_CANCELLED);
			$order->save();
			self::sendOrderEmails($request, $order, 'canceled');
		}
		if (session_id()) {
			$_SESSION['store_cancel'] = true;
			$_SESSION['store_cancel_exText'] = $request->getFormParam('exText', $request->getQueryParam('exText'));
			$_SESSION['store_return'] = null;
			unset($_SESSION['store_return']);
		}
		$backUrl = $request->getFormParam('store_cancel_backUrl', $request->getQueryParam('store_cancel_backUrl', $request->getUri()));
		StoreNavigation::redirect($backUrl);
		exit();
	}
	
	private static function gatewayBackMessage($type, $exText = null) {
		if ($type == 'return') {
			StoreCartApi::clearStoreCart();
			$alert = 'success';
			$text = StoreModule::__('Payment has been submitted');
		} else if ($type == 'cancel') {
			$alert = 'danger';
			$text = StoreModule::__('Payment has been canceled');
		}
		if (session_id()) { $sessionKey = 'store_'.$type; $_SESSION[$sessionKey] = null; unset($_SESSION[$sessionKey]); }
		$out = "<script type=\"text/javascript\">".
			"$('<div>')".
				".addClass('alert alert-{$alert}')".
				".css({"
					."position: 'fixed', "
					."right: '10px', "
					."top: '10px', "
					."zIndex: 100000, "
					."fontSize: '24px', "
					."padding: '30px 50px', "
					."lineHeight: '24px', "
					."maxWidth: '748px'"
				."})".
				".append('{$text}')".
				($exText ? ".append('<br />').append($('<span>').css({"
					."fontSize: '14px', "
					."lineHeight: '18px'"
				."}).append('".addslashes($exText)."'))" : "").
				".prepend($('<button>')".
					".addClass('close')".
					".css({marginRight: '-40px', marginTop: '-24px'})".
					".html(\"&nbsp;&times;\")".
					".on('click', function() {".
						"$(this).parent().remove();".
					"})".
				")".
				".appendTo('body');".
			"</script>";
		return $out;
	}
	
	private static function getGatewayIdFromRequest(StoreNavigation $request) {
		$gatewayId = $request->getQueryParam('gatewayId');
		if (!$gatewayId) $gatewayId = $request->getArg(1);
		return $gatewayId;
	}
	
	/**
	 * Get currently used gateway instance
	 * @param StoreNavigation $request store request descriptor object.
	 * @return PaymentGateway|null
	 */
	private static function getGateway(StoreNavigation $request) {
		if (!self::$gateway) {
			$gatewayId = self::getGatewayIdFromRequest($request);
			if ($gatewayId) {
				$cls = 'Gateway'.implode('', array_map('ucfirst', preg_split('#(?:_|\-|(\d))#', $gatewayId, -1, PREG_SPLIT_NO_EMPTY | PREG_SPLIT_DELIM_CAPTURE)));
				$dFile = dirname(__FILE__).'/PaymentGateway.php';
				$file = $request->basePath.'/'.$cls.'.php';
				if (!is_file($file)) $file = dirname(__FILE__).'/'.$cls.'.php';
				if (is_file($file) && is_file($dFile)) {
					$config = isset(StoreModule::$initData->gatewayConfig[$gatewayId]) ? StoreModule::$initData->gatewayConfig[$gatewayId] : null;
					if (!$config || !is_object($config)) $config = new stdClass();
					
					// Note: backwards compatibility, since usage of globals was part of public API.
					if (isset($config->gatewayId) && $config->gatewayId) {
						foreach ($config as $k => $v) {
							$vName = 'store_'.$config->gatewayId.'_'.$k;
							global $$vName;
							$$vName = $v;
						}
					}
					
					$config->wbBaseLang = $request->baseLang;
					$config->wbDefLang = $request->defLang;
					$config->wbLang = $request->lang;
					require_once($dFile);
					require_once($file);
					self::$gateway = new $cls($config);
				}
			}
		}
		return self::$gateway;
	}
	
	/**
	 * Format price according to price options
	 * @param float $price
	 * @return string
	 */
	public static function getFormattedPrice($price) {
		$currency = StoreData::getCurrency();
		$priceOpts = StoreData::getPriceOptions();
		$point = $priceOpts->decimalPoint ? $priceOpts->decimalPoint : '.';
		$places = $priceOpts->decimalPlaces ? $priceOpts->decimalPlaces : 2;
		$thousandsSep = $priceOpts->thousandsSeparator ? $priceOpts->thousandsSeparator : '';
		$prefix = $currency ? $currency->prefix : '';
		$postfix = $currency ? ($currency->postfix ? $currency->postfix : (($currency->code && !$prefix) ? ' '.$currency->code : '')) : '';
		return $prefix . number_format(floatval($price), $places, $point, $thousandsSep) . $postfix;
	}

	private static function getInvoiceUrl(StoreNavigation $request, StoreModuleOrder $order) {
		$lang = $request->lang;
		$request->lang = $request->defLang ? $request->defLang : $request->baseLang;
		$url = $request->getUrl("store-invoice/" . $order->getHash());
		$request->lang = $lang;
		return $url;
	}

	public static function getFileDownloadUrl(StoreNavigation $request, StoreModuleOrder $order) {
		$lang = $request->lang;
		$request->lang = $request->defLang ? $request->defLang : $request->baseLang;
		$url = $request->getUrl("store-file-download/" . $order->getHash());
		$request->lang = $lang;
		return $url;
	}

	/**
	 * @param StoreNavigation $request
	 * @return object
	 */
	private static function backupLang(StoreNavigation $request) {
		return (object) array(
			'lang' => $request->lang,
			'siteLang' => SiteModule::$lang,
		);
	}

	/**
	 * @param StoreNavigation $request
	 * @param object $langBackup
	 * @return void
	 */
	private static function restoreLang(StoreNavigation $request, $langBackup) {
		$request->lang = $langBackup->lang;
		SiteModule::setLang($langBackup->siteLang);
	}

	/**
	 * @param StoreNavigation $request
	 * @param string $lang
	 * @return void
	 */
	private static function setLang(StoreNavigation $request, $lang) {
		$request->lang = $lang;
		SiteModule::setLang($lang);
	}

	/** @return array|null */
	private static function getContactForm() {
		if (isset(StoreModule::$initData->contactFormId) && StoreModule::$initData->contactFormId) {
			$targetFormId = StoreModule::$initData->contactFormId;
			foreach (StoreModule::$siteInfo->forms as $pageForms) {
				foreach ($pageForms as $formId => $form) {
					if ($formId == $targetFormId) return $form;
				}
			}
		}
		return null;
	}

	/** @return array|null */
	private static function getBillingForm() {
		if (isset(StoreModule::$initData->billingFormId) && StoreModule::$initData->billingFormId) {
			$targetFormId = StoreModule::$initData->billingFormId;
			foreach (StoreModule::$siteInfo->forms as $pageForms) {
				foreach ($pageForms as $formId => $form) {
					if ($formId == $targetFormId) return $form;
				}
			}
		}
		return null;
	}

	private static function handleStockNotifications(StoreNavigation $request, StoreModuleOrder $order) {
		$stockSettings = StoreData::getStockSettings();
		if (!$stockSettings
				|| !$stockSettings->enableManagement
				|| !$stockSettings->sendLowStockNotifications) {
			return;
		}
		$triggerAmount = $stockSettings->notificationTriggerStockAmount ?: 0;
		if ($triggerAmount < 0) $triggerAmount = 0;

		$stockChanges = array();
		if ($order->isStockApplicable($stockSettings->applyVersion)) {
			StoreModuleOrder::indexStockChangesFromItems($order->getItems(), $stockChanges);
		}

		$notifyItems = array();
		foreach (StoreData::getItems() as $item) {
			if (!isset($item->sku) || !is_string($item->sku) || empty($item->sku)
					|| !isset($stockChanges[$item->sku])
					|| $stockChanges[$item->sku] <= 0
					|| ($item->quantity - $stockChanges[$item->sku]) > $triggerAmount) {
				continue;
			}

			$nItem = clone $item;
			$nItem->quantity -= $stockChanges[$item->sku];
			if ($nItem->quantity < 0) $nItem->quantity = 0;

			$notifyItems[] = $nItem;
		}

		if (empty($notifyItems)) return;
		$form = self::getContactForm();
		if (!$form) return;

		$langBackup = self::backupLang($request);
		{
			self::setLang($request, $request->defLang);
			self::sendMail(
					StoreModule::__('Low stock notification'),
					self::renderEmailView(
							$request,
							dirname(__FILE__).'/view/email-for-stock-notify.php',
							array(
								'title' => StoreModule::__('Low stock notification'),
								'items' => $notifyItems,
							)),
					$form, $request);
		}
		self::restoreLang($request, $langBackup);
	}

	protected static function sendOrderEmails(StoreNavigation $request, StoreModuleOrder $order, $type) {
		@set_time_limit(130);
		$subject = '';
		if ($type == 'complete') {
			$subject = sprintf(StoreModule::__("Payment received for order %s at %s"), '#'.$order->getTransactionId(), StoreModule::$siteInfo->prettyDomain);
		} else if ($type == 'pending') {
			$subject = sprintf(StoreModule::__("New order %s at %s"), '#'.$order->getTransactionId(), StoreModule::$siteInfo->prettyDomain);
		} else if ($type == 'canceled') {
			$subject = sprintf(StoreModule::__("Order %s canceled at %s"), '#'.$order->getTransactionId(), StoreModule::$siteInfo->prettyDomain);
		}
		if (!$subject) return;
		$form = self::getContactForm();
		if (!$form) return;

		$langBackup = self::backupLang($request);
		{
			self::setLang($request, $request->defLang); // Force sending email to seller in default language.
			self::sendMail($subject, self::prepareSellerMailBody($request, $subject, $order, $type), $form, $request);

			self::setLang($request, $order->getLang() ?: $request->defLang); // Force sending email to customer in language of the order.
			$billingInfo = $order->getBillingInfo();
			if ($billingInfo) {
				$form["email"] = $billingInfo->email;
				self::sendMail($subject, self::prepareBuyerMailBody($request, $subject, $order, $type), $form, $request);
			}
		}
		self::restoreLang($request, $langBackup);
	}


	/**
	 * Generate email body
	 * @param StoreNavigation $request
	 * @param string $title
	 * @param StoreModuleOrder $order
	 * @param string $type
	 * @return string
	 */
	private static function prepareSellerMailBody(StoreNavigation $request, $title, StoreModuleOrder $order, $type) {
		return self::prepareMailBody('seller', $request, $title, $order, $type);
	}

	/**
	 * Generate email body
	 * @param StoreNavigation $request
	 * @param string $title
	 * @param StoreModuleOrder $order
	 * @param string $type
	 * @return string
	 */
	private static function prepareBuyerMailBody(StoreNavigation $request, $title, StoreModuleOrder $order, $type) {
		return self::prepareMailBody('buyer', $request, $title, $order, $type);
	}
	
	private static function prepareMailBody($forType, StoreNavigation $request, $title, StoreModuleOrder $order, $type) {
		$typeText = ''; $phraseText = '';
		if ($type == 'complete') {
			$typeText = StoreModule::__('Complete');
			$phraseText = StoreModule::__('Thank you for your purchase.');
		} else if ($type == 'pending') {
			$typeText = StoreModule::__('Pending');
		} else if ($type == 'canceled') {
			$typeText = StoreModule::__('Canceled');
		}
		return self::renderEmailView($request, dirname(__FILE__).'/view/email-for-'.$forType.'.php', array(
			"title" => $title,
			"order" => $order,
			"type" => $type,
			"typeText" => $typeText,
			"phraseText" => $phraseText,
			"invoiceUrl" => self::getInvoiceUrl($request, $order),
			"gatewayName" => self::getGatewayName($order->getGatewayId()),
			"fileDownloadUrl" => self::getFileDownloadUrl($request, $order),
		));
	}
	
	private static function getGatewayName($gatewayId) {
		if ($gatewayId == 'CashOnDelivery') {
			$gatewayName = StoreModule::__('Cash on delivery');
		} else if ($gatewayId == 'BankTransfer') {
			$gatewayName = StoreModule::__('Bank transfer');
		} else if ($gatewayId == 'YandexKassa') {
			$gatewayName = 'ЮКасса';
		} else {
			$gatewayName = $gatewayId;
		}
		return $gatewayName;
	}

	private static function renderEmailView(StoreNavigation $request, $viewPath, $vars) {
		extract($vars);

		ob_start();
		include $viewPath;
		$content = ob_get_clean();

		if( !isset($title) && isset($subject) )
			$title = $subject;
		ob_start();
		include $request->basePath.'/src/view/email_layout.php';
		return ob_get_clean();
	}

	public static function buildInfoHtmlTableRows($title, $info, $useBillingForm = false) {
		try {
			$hasAny = false;
			$rows = array();
			if ($info && (is_array($info) || is_object($info))) {
				foreach ($info as $k => $v) {
					if (empty($v)) continue;
					$field = self::getBillingFieldByKey($k);
					$fieldName = self::getInfoHtmlTableFieldName($k);
					$fieldValue = self::getInfoHtmlTableFieldValue($v, $useBillingForm ? $k : null);
					if ($fieldName === null) continue;
					if (!$hasAny) {
						$rows[] = '<tr><td colspan="2"><h3>' . $title . ':</h3></td></tr>';
						$hasAny = true;
					}
					$rows[] = '<tr>' .
						'<td><strong>' . $fieldName . ($fieldValue === false ? '' : ':') . '</strong>&nbsp;</td>' .
						($fieldValue === false ? '' : ('<td>' . (($field && $field->type === 'file') ? $fieldValue : htmlspecialchars($fieldValue)) . '</td>')) .
						'</tr>';
				}
			} else if (is_string($info)) {
				$hasAny = true;
				$rows[] = '<tr><td colspan="2"><h3>' . $title . ':</h3></td></tr>';
				$rows[] = '<tr><td colspan="2">' . $info . '</td></tr>';
			}
			if ($hasAny) $rows[] = '<tr><td colspan="2">&nbsp;</td></tr>';
			return implode("\n", $rows);
		} catch (\Exception $e) {
			var_dump($e);die();
		}
	}

	public static function getInfoHtmlTableFieldValue($v, $key)
	{
		if ($key) {
			$billingForm = StoreData::getBillingForm();
			if ($billingForm && strpos($key, 'wb_input_') === 0) {
				$idx = str_replace('wb_input_', '', $key);
				if (isset($billingForm->content->fields[$idx])) {
					$field = $billingForm->content->fields[$idx];

					if ($field->type === 'checkbox' && (!isset($field->settings->options) || count($field->settings->options) <= 0 || (count($field->settings->options) === 1 && empty($field->settings->options[0])))) {
						return false;
					}
					if ($field->type === 'range') {
						return $v;
					}
					if ($field->type === 'file') {
						$protocol = isHttps() ? 'https' : 'http';
						$host = (isset($_SERVER['HTTP_HOST']) && $_SERVER['HTTP_HOST']) ? $_SERVER['HTTP_HOST'] : '127.0.0.1';
						$url = $protocol.'://'.$host;

						if (is_array($v)) {
							foreach ($v as &$i) {
								$i = '<a target="_blank" href="' . $url . '/forms_log_attachments' . $i . '">' . basename($i) . '</a>';
							}
						} else {
							$v = '<a target="_blank" href="' . $url . '/forms_log_attachments' . $v . '">' . basename($v) . '</a>';
						}
					}
				}
			}
		}

		if (is_array($v)) {
			return implode(', ', $v);
		}
		return $v;
	}
	
	public static function getInfoHtmlTableFieldName($k) {
		if( $k === "isCompany" )
			return null;
		
		if ($k === 'email') return StoreModule::__('Email');
		if ($k === 'companyName') return StoreModule::__('Company Name');
		if ($k === 'companyCode') return StoreModule::__('Company Code');
		if ($k === 'companyVatCode') return StoreModule::__('Company TAX/VAT number');
		if ($k === 'firstName') return StoreModule::__('First Name');
		if ($k === 'lastName') return StoreModule::__('Last Name');
		if ($k === 'address1' || $k === 'address2') return StoreModule::__('Address');
		if ($k === 'city') return StoreModule::__('City');
		if ($k === 'region') return StoreModule::__('Region');
		if ($k === 'postCode') return StoreModule::__('Post Code');
		if ($k === 'countryCode') return StoreModule::__('Country Code');
		if ($k === 'country') return StoreModule::__('Country');
		if ($k === 'phone') return StoreModule::__('Phone Number');

		$billingForm = StoreData::getBillingForm();
		if ($billingForm && strpos($k, 'wb_input_') === 0) {
			$idx = str_replace('wb_input_', '', $k);
			if (isset($billingForm->content->fields[$idx])) {
				return StoreModule::__htmlToText(StoreModule::__tr($billingForm->content->fields[$idx]->name));
			}
		}
		
		return (function_exists('mb_ucfirst') ? mb_ucfirst($k) : ucfirst($k));
	}

	public static function getBillingFieldByKey($key)
	{
		$billingForm = StoreData::getBillingForm();
		if ($billingForm && strpos($key, 'wb_input_') === 0) {
			$idx = str_replace('wb_input_', '', $key);
			if (isset($billingForm->content->fields[$idx])) {
				return $billingForm->content->fields[$idx];
			}
		}
		return null;
	}
	
	/**
	 * @param string $text
	 * @return string
	 */
	public static function safeEmailText($text) {
		$result = str_replace(array('<s>', '</s>'), array('[s]', '[/s]'), $text);
		$result = htmlspecialchars($result);
		$result = str_replace(array('[s]', '[/s]'), array('<s>', '</s>'), $result);
		return $result;
	}

	/**
	 * Send email to site owner
	 * @param string $subject
	 * @param string $body
	 * @param array $options
	 */
	private static function sendMail($subject, $body, $options, StoreNavigation $request) {
		try {
			requirePHPMailer();
		} catch (ErrorException $ex) {
			error_log($ex->getMessage());
		}
		$mailer = new PHPMailer();
		if (isset($options['smtpEnable']) && $options['smtpEnable'] && isset($options['smtpHost']) && $options['smtpHost']) {
			/* $mailer->Debugoutput = function($string) {
				file_put_contents(__DIR__.'/smtp-debug.log', $string."\n", FILE_APPEND);
			};
			$mailer->SMTPDebug = 4; */
			$mailer->isSMTP();
			$mailer->Host = ((isset($options['smtpHost']) && $options['smtpHost']) ? $options['smtpHost'] : 'localhost');
			$mailer->Port = ((isset($options['smtpPort']) && intval($options['smtpPort'])) ? intval($options['smtpPort']) : 25);
			$mailer->SMTPSecure = ((isset($options['smtpEncryption']) && $options['smtpEncryption']) ? $options['smtpEncryption'] : '');
			$mailer->SMTPAutoTLS = false;
			if (isset($options['smtpUsername']) && $options['smtpUsername'] && isset($options['smtpPassword']) && $options['smtpPassword']) {
				$mailer->SMTPAuth = true;
				$mailer->Username = ((isset($options['smtpUsername']) && $options['smtpUsername']) ? $options['smtpUsername'] : '');
				$mailer->Password = ((isset($options['smtpPassword']) && $options['smtpPassword']) ? $options['smtpPassword'] : '');
			}
			$mailer->SMTPOptions = array('ssl' => array(
				'verify_peer' => false,
				'verify_peer_name' => false,
				'allow_self_signed' => true
			));
		}
		$optsObject = json_decode($options['object'], true);
		$sender_name = $optsObject['sender_name'];
		$sender_email = (isset($options['emailFrom']) && $options['emailFrom']) ? trim($options['emailFrom']) : $optsObject['sender_email'];
		if (preg_match('#^([^<]+|)<([^>]+)>$#', $sender_email, $m)) {
			if (trim($m[1])) $sender_name = trim($m[1]);
			$sender_email = trim($m[2]);
		} else if (preg_match('#^<([^>]+)>(.+|)$#', $sender_email, $m)) {
			if (trim($m[2])) $sender_name = trim($m[2]);
			$sender_email = trim($m[1]);
		}
		if ($sender_name == '__default__') { $sender_name = StoreModule::__('Store Notification System'); }
		$mailer->SetFrom($sender_email, $sender_name);
		$mailTo = array_map('trim', preg_split('#[;,]#', $options['email'] ?: '', -1, PREG_SPLIT_NO_EMPTY));
		foreach ($mailTo as $eml) {
			if ($eml && ($m = is_mail($eml))) $mailer->AddAddress($m);
		}
		$mailer->CharSet = 'utf-8';
		$mailer->msgHTML($body);
		$mailer->AltBody = strip_tags(str_replace("</tr>", "</tr>\n", preg_replace('#<(style|head).*>.*</\\1>#isuU', '', $body)));
		$mailer->Subject = $subject ? $subject : $options['subject'];
		ob_start();
		$res = $mailer->Send();
		ob_get_clean();
		if (!$res && $mailer->ErrorInfo) {
			error_log('[Form sending error]: '.$mailer->ErrorInfo);
		}
	}

	/**
	 * @param StoreNavigation $request
	 * @param bool $homePage
	 * @return array{hr_out: string|null, requestHandled: bool}
	 */
	public static function process(StoreNavigation $request, $homePage = false) {
		$handledRequest = false;
		if ($homePage) {
			$ctrl = new self();
			$key = $request->getArg(0) ?: '';
			$cartAction = array_map('ucfirst', explode('-', strtolower(preg_replace('#[^a-zA-Z0-9\-]+#', '', $key))));
			$cartAction[0] = strtolower($cartAction[0]);
			$method = implode('', $cartAction).'Action';
			if (method_exists($ctrl, $method) && strpos($method, 'feedxmlAction') === false) {
				call_user_func(array($ctrl, $method), $request);
				$handledRequest = true;
			} else if ($request) {
				$feedsID = sprintf("%08x", crc32(StoreModule::$siteInfo->websiteUID));
				$method2 = $request->getArg(1) ? strtolower(preg_replace('#[^a-zA-Z0-9\-]+#', '', $request->getArg(1))) . 'Action' : '';
				// Check if action is products feed action
				if ($key === $feedsID && strpos($method2, 'feedxmlAction') !== false && method_exists($ctrl, $method2)) {
					call_user_func(array($ctrl, $method2), $request);
					$handledRequest = true;
				}
				else {
					$gateway = self::getGateway($request);
					if ($gateway && method_exists($gateway, $key)) {
						StoreModule::respondWithJson(call_user_func(array($gateway, $key))); // this method exits the process
					}
				}
			}
		}
		if (session_id() && isset($_SESSION['store_return'])) {
			return array(self::gatewayBackMessage('return'), true);
		}
		if (session_id() && isset($_SESSION['store_cancel'])) {
			$exText = (isset($_SESSION['store_cancel_exText']) && $_SESSION['store_cancel_exText'])
					? $_SESSION['store_cancel_exText'] : null;
			$_SESSION['store_cancel_exText'] = null;
			unset($_SESSION['store_cancel_exText']);
			return array(self::gatewayBackMessage('cancel', $exText), true);
		}
		return array(null, $handledRequest);
	}

	private function publicDecrypt($encData) {
		require_once __DIR__.'/../../phpseclib/Crypt/Random.php'; // spell-checker: ignore phpseclib
		require_once __DIR__.'/../../phpseclib/Math/BigInteger.php';
		require_once __DIR__.'/../../phpseclib/Crypt/Hash.php';
		require_once __DIR__.'/../../phpseclib/Crypt/RSA.php';
		$rsa = new \phpseclib\Crypt\RSA();
		$rsa->loadKey($this->getSecurityPublicKey());
		$rsa->setEncryptionMode(\phpseclib\Crypt\RSA::ENCRYPTION_PKCS1);
		$data = @$rsa->decrypt(base64_decode($encData));
		return ($data === false) ? null : $data;
	}

	private function publicEncrypt($data) {
		require_once __DIR__.'/../../phpseclib/Crypt/Random.php';
		require_once __DIR__.'/../../phpseclib/Math/BigInteger.php';
		require_once __DIR__.'/../../phpseclib/Crypt/Hash.php';
		require_once __DIR__.'/../../phpseclib/Crypt/RSA.php';
		$rsa = new \phpseclib\Crypt\RSA();
		$rsa->loadKey($this->getSecurityPublicKey());
		$rsa->setEncryptionMode(\phpseclib\Crypt\RSA::ENCRYPTION_PKCS1);
		$encData = @$rsa->encrypt($data);
		return ($encData === false) ? null : base64_encode($encData);
	}

	private function getSecurityPublicKey() {
		return "-----BEGIN PUBLIC KEY-----\n"
		// spell-checker: disable
		."MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAzeio9jpU3e31Rlc4w0SA\n"
		."jOWOkjS++yZnyaziUDyLXupLxELER2SHyA2nFG7eOuKPohYFomX/GQdtbMLLL+4J\n"
		."/IofyOi1t/jlafY3wzTYCN2u8pfYP6L5sChuE3zb+g7Gvq/1XewiroDChy0mE+zr\n"
		."mATJp+UY2zcc60S0aiv+mFaGHrD6vyK/uUlfd2XbLNjWJnOe4HKq/uZb9MK8yY34\n"
		."snpLzrwmnxjS0/UDvljdrUAA1gIYA8rIO08AiyT9evTQEMyp4861COfGVdASHi/i\n"
		."O5piPRMp1BuY0LYk0ykA79gI7kygk5qQRcHJLZ1jhsm4jHl7chrjJ3jis8Pk4ico\n"
		."KwIDAQAB\n"
		// spell-checker: enable
		."-----END PUBLIC KEY-----\n";
	}

	public function googleFeedXmlAction() {
		header('Content-Type: text/xml');
		echo StoreData::generateGoogleFeed();
		exit();
	}

	public function facebookFeedXmlAction() {
		header('Content-Type: text/xml');
		echo StoreData::generateFacebookFeed();
		exit();
	}

	public function yandexFeedXmlAction() {
		header('Content-Type: text/xml');
		echo StoreData::generateYandexFeed();
		exit();
	}
}
