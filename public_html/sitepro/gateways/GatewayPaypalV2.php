<?php

class GatewayPaypalV2 extends PaymentGateway
{
	protected $returnAfterCallback = true;

	/** @var \GatewayPaypalV2Auth */
	private $auth;

	/** @var \PayPal\Rest\ApiContext */
	private $apiContext;

	const TRANSACTION_ID_KEY = 'txnId';

	public function init()
	{
		require_once __DIR__ . '/PayPal-PHP-SDK/autoload.php';
		$this->authorize($this->config);
		return parent::init();
	}

	public function doReturnAfterCallback() {
		return $this->returnAfterCallback;
	}

	private function authorize(stdClass $config = null)
	{
		if (($input = $this->getFormParam('input'))) {
			$this->auth = \GatewayPaypalV2Auth::parseFromString($input);
		} else {
			$clientId = null;
			$clientSecret = null;
			$demo = null;
			if (isset($config->clientId) && $config->clientId) {
				$clientId = $config->clientId;
			}
			if (isset($config->clientSecret) && $config->clientSecret) {
				$clientSecret = $config->clientSecret;
			}
			if (isset($config->demo) && $config->demo) {
				$demo = $config->demo;
			}
			$this->auth = new \GatewayPaypalV2Auth($clientId, $clientSecret, $demo);
		}
	}

	/** @return \PayPal\Rest\ApiContext */
	private function getApiContext()
	{
		if (!$this->apiContext) {
			$this->apiContext = new \PayPal\Rest\ApiContext(
				new \PayPal\Auth\OAuthTokenCredential(
					$this->auth->clientId, // ClientID
					$this->auth->clientSecret // ClientSecret
				)
			);
			$this->apiContext->setConfig(array(
				'mode' => $this->auth->demo ? 'sandbox' : 'live',
			));
		}
		return $this->apiContext;
	}

	public function requestCreatePayment()
	{
		$this->authorize();
		$resp = array();
		try {
			$resp['url'] = $this->getPaymentUrl($_POST, 'button');
		} catch (Exception $ex) {
			$resp['error'] = $ex->getMessage();
		}
		return $resp;
	}

	public function createInstantRedirectUrl($formVars)
	{
		try {
			return $this->getPaymentUrl($formVars, 'store');
		} catch (\PayPal\Exception\PayPalConnectionException $ex) {
			$this->setLastError($ex->getMessage());
			error_log("Paypal connection error: {$ex->getData()}");
		} catch (Exception $ex) {
			$this->setLastError($ex->getMessage());
		}
		return null;
	}

	private function getPaymentUrl(array $params, $from)
	{
		if (!isset($params['amount']) || !$params['amount']) throw new ErrorException('Amount is not specified');
		if (!isset($params['currency']) || !$params['currency']) throw new ErrorException('Currency is not specified');
		if (!isset($params['description']) || !trim($params['description'])) throw new ErrorException('Description is not specified');
		$transactionId = (isset($params['transactionId']) && $params['transactionId']) ? $params['transactionId'] : md5(microtime());

		$returnUrl = (isset($params['returnUrl']) && $params['returnUrl'])
			? $params['returnUrl'] : (getBaseUrl() . 'store-callback/Paypal');
		$returnUrl .= '?txnId=' . $transactionId;
		$cancelUrl = (isset($params['cancelUrl']) && $params['cancelUrl'])
			? $params['cancelUrl'] : (getBaseUrl() . 'store-cancel/Paypal');
		$cancelUrl .= '?txnId=' . $transactionId;

		$cartData = $from == 'store' ? StoreData::getCartData() : null;

		$payer = new \PayPal\ApiV2\Payer();
		$payer->setPaymentMethod('paypal');

		$payerInfo = new \PayPal\ApiV2\PayerInfo();
		if ($cartData && $cartData->billingInfo) {
			$payerInfo->setEmail($cartData->billingInfo->email);
		}

		$payer->setPayerInfo($payerInfo);

		$items = new \PayPal\ApiV2\ItemList();
		$totalItemsPrice = 0;
		if ($cartData) {
			if (isset($cartData->items) && is_array($cartData->items)) {
				foreach ($cartData->items as $item) {
					$totalItemsPrice += $item->price * $item->quantity;

					$itemAmount = new \PayPal\ApiV2\Amount();
					$itemAmount->setValue($item->price);
					$itemAmount->setCurrencyCode($params['currency']);

					$name = html_entity_decode(strip_tags(tr_($item->name)));
					if (mb_strlen($name) > 127) {
						$name = mb_substr($name, 0, 124) . '...';
					}

					$description = mb_substr(html_entity_decode(strip_tags(tr_($item->description))), 0, 2048);
					if (mb_strlen($description) > 2048) {
						$description = mb_substr($description, 0, 2045) . '...';
					}

					$url = '';
					if (isset($item->alias)) {
						$url = str_replace('http://', 'https://', getBaseUrl()) . rawurlencode(StoreModule::__tr($item->alias));
					}

					$items->addItem(
						(new \PayPal\ApiV2\Item())
							->setCurrency($params['currency'])
							->setName($name)
							->setDescription($description)
							->setUrl($url)
							->setUnitAmount($itemAmount)
							->setQuantity((string)$item->quantity)
					);
				}
			}

			$shippingCost = $params['amount'] - $totalItemsPrice;
			$shippingName = StoreModule::__('Shipping');
			if ($shippingCost > 0) {
				$shippingMethods = StoreData::getShippingMethods($cartData->billingInfo);
				if (count($shippingMethods) && isset($cartData->shippingMethodId)) {
					foreach ($shippingMethods as $method) {
						if ($method->id == $cartData->shippingMethodId) {
							$shippingName = $method->name;
						}
					}
				}

				$itemAmount = new \PayPal\ApiV2\Amount();
				$itemAmount->setValue($shippingCost);
				$itemAmount->setCurrencyCode($params['currency']);

				$description = html_entity_decode($shippingName);
				if (mb_strlen($description) > 2048) {
					$description = mb_substr($description, 0, 2045) . '...';
				}

				$items->addItem(
					(new \PayPal\ApiV2\Item())
						->setCurrency($params['currency'])
						->setName(StoreModule::__('Shipping'))
						->setDescription($description)
						->setUnitAmount($itemAmount)
						->setQuantity('1')
				);
			}
		} else {

			$name = html_entity_decode(strip_tags($params['description']));
			if (mb_strlen($name) > 127) {
				$name = mb_substr($name, 0, 124) . '...';
			}

			$description = mb_substr(html_entity_decode(strip_tags($params['description'])), 0, 2048);
			if (mb_strlen($description) > 2048) {
				$description = mb_substr($description, 0, 2045) . '...';
			}

			$itemAmount = new \PayPal\ApiV2\Amount();
			$itemAmount->setValue($params['amount']);
			$itemAmount->setCurrencyCode($params['currency']);
			$items->addItem(
				(new \PayPal\ApiV2\Item())
					->setCurrency($params['currency'])
					->setName($name)
					->setDescription($description)
					->setUnitAmount($itemAmount)
					->setQuantity('1')
			);

			if (isset($params['shipping']) && $params['shipping']) {
				$name = html_entity_decode(strip_tags($params['shipping']));
				if (mb_strlen($name) > 127) {
					$name = mb_substr($name, 0, 124) . '...';
				}

				$description = mb_substr(html_entity_decode(strip_tags($params['shipping'])), 0, 2048);
				if (mb_strlen($description) > 2048) {
					$description = mb_substr($description, 0, 2045) . '...';
				}

				$itemAmount = new \PayPal\ApiV2\Amount();
				$itemAmount->setValue(0);
				$itemAmount->setCurrencyCode($params['currency']);
				$items->addItem(
					(new \PayPal\ApiV2\Item())
						->setCurrency($params['currency'])
						->setName($name)
						->setDescription($description)
						->setUnitAmount($itemAmount)
						->setQuantity('1')
				);
			}
		}

		$sumItemsAmount = 0;
		foreach ($items as $item) {
			$sumItemsAmount += $item->getUnitAmount() * $item->getQuantity();
		}
		if ((float)$sumItemsAmount !== (float)$params['amount']) {
			$itemAmount = new \PayPal\ApiV2\Amount();
			$itemAmount->setValue($params['amount']);
			$itemAmount->setCurrencyCode($params['currency']);
			$items->setItems([
				(new \PayPal\ApiV2\Item())
					->setCurrency($params['currency'])
					->setName('Cart contents')
					->setDescription('Cart contents')
					->setUnitAmount($itemAmount)
					->setQuantity('1')
			]);
		}

		$itemAmount = new \PayPal\ApiV2\Amount();
		$itemAmount->setValue($params['amount']);
		$itemAmount->setCurrencyCode($params['currency']);

		$breakdown = new \PayPal\ApiV2\Breakdown();
		$breakdown->setItemTotal($itemAmount);

		$amount = new \PayPal\ApiV2\Amount();
		$amount->setValue($params['amount']);
		$amount->setCurrencyCode($params['currency']);
		$amount->setBreakdown($breakdown);
		$items->setAmount($amount);

		$experienceContext = new \PayPal\ApiV2\ExperienceContext();
		$experienceContext->setCancelUrl($cancelUrl);
		$experienceContext->setReturnUrl($returnUrl);

		$paypal = new \PayPal\ApiV2\Paypal();
		$paypal->setExperienceContext($experienceContext);

		$paymentSource = new \PayPal\ApiV2\PaymentSource();
		$paymentSource->setPaypal($paypal);

		$payment = new \PayPal\ApiV2\Payment();
		$payment->setIntent('CAPTURE')
			->setPayer($payer)
			->setPurchaseUnits(array($items))
			->setPaymentSource($paymentSource);

		$payment->create($this->getApiContext());
		if ($payment->getId()) {
			$_SESSION[self::TRANSACTION_ID_KEY] = $payment->getId();
			if ($order = StoreModuleOrder::findByTransactionId($transactionId)) {
				$order->setExtTransactionId($payment->getId());
				$order->save();
			}
		}
		return $payment->getApprovalLink();
	}

	public function getTransactionId()
	{
		$transactionId = $this->getQueryParam('txnId');
		if ($transactionId) {
			/* @var $order StoreModuleOrder */
			$order = $transactionId ? StoreModuleOrder::findByTransactionId($transactionId) : null;
			if ($order) {
				return $order->getTransactionId();
			}
		} else {
			$webhook = new \PayPal\Api\WebhookEvent(file_get_contents('php://input'));
			if ($webhook && $webhook->getId()) {
				try {
					$webhook = \PayPal\Api\WebhookEvent::get($webhook->getId(), $this->getApiContext());
				} catch (\Exception $e) {
					$webhook = null;
				}
			} else {
				$webhook = null;
			}
			if ($webhook && $webhook->getResourceType() === 'checkout-order') {
				$extTransactionId = $webhook->getResource()->id;
				$order = StoreModuleOrder::findByExtTransactionId($extTransactionId);
				if ($order) {
					return $order->getTransactionId();
				}
			}
		}
		return null;
	}

	public function callback(StoreModuleOrder $order = null)
	{
		if (!$order) {
			$url = getBaseUrl().'store-return/PayPal';
			header('Location: '.$url, true, 302);
			exit();
		} elseif ($order->getExtTransactionId()) {
			$payment = \PayPal\ApiV2\Payment::get($order->getExtTransactionId(), $this->getApiContext());
		} elseif (isset($_SESSION[self::TRANSACTION_ID_KEY])) {
			$payment = \PayPal\ApiV2\Payment::get($_SESSION[self::TRANSACTION_ID_KEY], $this->getApiContext());
			unset($_SESSION[self::TRANSACTION_ID_KEY]);
			$_SESSION[self::TRANSACTION_ID_KEY] = null;
		}

		if (isset($payment) && $payment) {
			if ($payment->getStatus() === 'APPROVED') {
				$payment = $payment->capture($this->getApiContext());
			}
			if ($payment->getStatus() === 'COMPLETED') {
				$paymentSuccess = true;
				foreach ($payment->getPurchaseUnits() as $item) {
					if (!isset($item->payments['captures']) || !is_array($item->payments['captures'])) continue;
					foreach ($item->payments['captures'] as $capture) {
						if ($capture['status'] !== 'COMPLETED') {
							$paymentSuccess = false;
						}
						switch ($capture['status']) {
							case 'DECLINED':
								$order->setState(StoreModuleOrder::STATE_CANCELLED);
								$order->save();
								return false;
							case 'REFUNDED':
								$order->setState(StoreModuleOrder::STATE_REFUNDED);
								$order->save();
								return false;
							case 'FAILED':
								$order->setState(StoreModuleOrder::STATE_FAILED);
								$order->save();
								return false;
							case 'PENDING':
								$order->setState(StoreModuleOrder::STATE_PENDING);
								$order->save();
								return false;
						}
					}
				}
				if ($paymentSuccess) {
					return true;
				}
			}
		}
		return false;
	}
}

class GatewayPaypalV2Auth
{

	public $clientId;
	public $clientSecret;
	public $demo;

	private static $instance;

	public function __construct($clientId = null, $clientSecret = null, $demo = false)
	{
		$this->clientId = $clientId;
		$this->clientSecret = $clientSecret;
		$this->demo = (bool)$demo;
	}

	public static function getInstance($shopId = null, $secretKey = null, $demo = false)
	{
		if (!self::$instance) {
			self::$instance = new self($shopId, $secretKey, $demo);
		}
		return self::$instance;
	}

	/**
	 * Decodes auth string and returns object.
	 * @param string|null $string Encoded auth string
	 * @return GatewayPaypalV2Auth
	 */
	public static function parseFromString($string = null)
	{
		for ($i = 0; $i < strlen($string) - 1; $i++) {
			if ($i % 4 == 0) {
				$ch = $string[$i];
				if (is_numeric($ch)) {
					$string[$i] = 10 - intval($ch);
				} else {
					$string[$i] = (strtoupper($ch) === $ch) ? strtolower($ch) : strtoupper($ch);
				}
			}
		}
		$arr = explode(':', base64_decode($string));
		if (count($arr) != 3) {
			return null;
		}
		$obj = new self();
		foreach ($arr as $idx => $part) {
			if ($idx == 0) $obj->clientId = $part;
			else if ($idx == 1) $obj->clientSecret = $part;
			else if ($idx == 2) $obj->demo = $part == '1';
		}
		return $obj;
	}

	/**
	 * Encodes self and returns auth string.
	 * @return string
	 */
	public function parseFromObject()
	{
		$string = base64_encode(implode(':', array($this->clientId, $this->clientSecret, ($this->demo ? '1' : '0'))));
		for ($i = 0; $i < strlen($string) - 1; $i++) {
			if ($i % 4 == 0) {
				$ch = $string[$i];
				if (is_numeric($ch)) {
					$string[$i] = 10 - intval($ch);
				} else {
					$string[$i] = (strtoupper($ch) === $ch) ? strtolower($ch) : strtoupper($ch);
				}
			}
		}
		return $string;
	}

}
