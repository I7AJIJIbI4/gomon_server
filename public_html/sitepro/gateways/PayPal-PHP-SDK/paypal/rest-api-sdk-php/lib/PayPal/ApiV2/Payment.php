<?php

namespace PayPal\ApiV2;

use PayPal\Common\PayPalResourceModel;
use PayPal\Core\PayPalConstants;
use PayPal\Rest\ApiContext;
use PayPal\Validation\ArgumentValidator;

/**
 * Class Payment
 *
 * Lets you create, process and manage payments.
 *
 * @package PayPal\ApiV2
 *
 * @property string id
 * @property string intent
 * @property \PayPal\ApiV2\ItemList[] purchase_units
 * @property \PayPal\ApiV2\Payer payer
 * @property \PayPal\ApiV2\PaymentSource payment_source
 * @property \PayPal\ApiV2\Payer application_context
 * @property string status
 *
 * @property string create_time
 * @property string update_time
 * @property \PayPal\ApiV2\Links[] links
 */
class Payment extends PayPalResourceModel
{
	/**
	 * Identifier of the payment resource created.
	 *
	 * @param string $id
	 *
	 * @return $this
	 */
	public function setId($id)
	{
		$this->id = $id;
		return $this;
	}

	/**
	 * Identifier of the payment resource created.
	 *
	 * @return string
	 */
	public function getId()
	{
		return $this->id;
	}

	/**
	 * Payment intent.
	 * Valid Values: ["CAPTURE", "AUTHORIZE"]
	 *
	 * @param string $intent
	 *
	 * @return $this
	 */
	public function setIntent($intent)
	{
		$this->intent = $intent;
		return $this;
	}

	/**
	 * Payment intent.
	 *
	 * @return string
	 */
	public function getIntent()
	{
		return $this->intent;
	}

	/**
	 * Source of the funds for this payment represented by a PayPal account or a direct credit card.
	 *
	 * @param \PayPal\ApiV2\Payer $payer
	 *
	 * @return $this
	 */
	public function setPayer($payer)
	{
		$this->payer = $payer;
		return $this;
	}

	/**
	 * Source of the funds for this payment represented by a PayPal account or a direct credit card.
	 *
	 * @return \PayPal\ApiV2\Payer
	 */
	public function getPayer()
	{
		return $this->payer;
	}

	/**
	 * @param \PayPal\ApiV2\PaymentSource $payment_source
	 *
	 * @return $this
	 */
	public function setPaymentSource($payment_source)
	{
		$this->payment_source = $payment_source;
		return $this;
	}

	/**
	 * @return \PayPal\ApiV2\PaymentSource
	 */
	public function getPaymentSource()
	{
		return $this->payment_source;
	}

	/**
	 * Transactional details including the amount and item details.
	 *
	 * @param \PayPal\ApiV2\ItemList[] $purchase_units
	 *
	 * @return $this
	 */
	public function setPurchaseUnits($purchase_units)
	{
		$this->purchase_units = $purchase_units;
		return $this;
	}

	/**
	 * Transactional details including the amount and item details.
	 *
	 * @return \PayPal\ApiV2\ItemList[]
	 */
	public function getPurchaseUnits()
	{
		return $this->purchase_units;
	}

	/**
	 * Append Purchase Unit to the list.
	 *
	 * @param \PayPal\ApiV2\ItemList $transaction
	 * @return $this
	 */
	public function addPurchaseUnit($purchase_unit)
	{
		if (!$this->getPurchaseUnits()) {
			return $this->setPurchaseUnits(array($purchase_unit));
		} else {
			return $this->setPurchaseUnits(
				array_merge($this->getPurchaseUnits(), array($purchase_unit))
			);
		}
	}

	/**
	 * Remove Purchase Unit from the list.
	 *
	 * @param \PayPal\ApiV2\ItemList $purchase_units
	 * @return $this
	 */
	public function removePurchaseUnit($purchase_unit)
	{
		return $this->setPurchaseUnits(
			array_diff($this->getPurchaseUnits(), array($purchase_unit))
		);
	}

	/**
	 * The status of the payment, authorization, or order transaction. The value is:<ul><li><code>created</code>. The transaction was successfully created.</li><li><code>approved</code>. The buyer approved the transaction.</li><li><code>failed</code>. The transaction request failed.</li></ul>
	 * Valid Values: ["created", "approved", "failed", "partially_completed", "in_progress"]
	 *
	 * @param string $status
	 *
	 * @return $this
	 */
	public function setStatus($status)
	{
		$this->status = $status;
		return $this;
	}

	/**
	 * The status of the payment, authorization, or order transaction. The value is:<ul><li><code>created</code>. The transaction was successfully created.</li><li><code>approved</code>. The buyer approved the transaction.</li><li><code>failed</code>. The transaction request failed.</li></ul>
	 *
	 * @return string
	 */
	public function getStatus()
	{
		return $this->status;
	}

	/**
	 * Payment creation time as defined in [RFC 3339 Section 5.6](http://tools.ietf.org/html/rfc3339#section-5.6).
	 *
	 * @param string $create_time
	 *
	 * @return $this
	 */
	public function setCreateTime($create_time)
	{
		$this->create_time = $create_time;
		return $this;
	}

	/**
	 * Payment creation time as defined in [RFC 3339 Section 5.6](http://tools.ietf.org/html/rfc3339#section-5.6).
	 *
	 * @return string
	 */
	public function getCreateTime()
	{
		return $this->create_time;
	}

	/**
	 * Payment update time as defined in [RFC 3339 Section 5.6](http://tools.ietf.org/html/rfc3339#section-5.6).
	 *
	 * @param string $update_time
	 *
	 * @return $this
	 */
	public function setUpdateTime($update_time)
	{
		$this->update_time = $update_time;
		return $this;
	}

	/**
	 * Payment update time as defined in [RFC 3339 Section 5.6](http://tools.ietf.org/html/rfc3339#section-5.6).
	 *
	 * @return string
	 */
	public function getUpdateTime()
	{
		return $this->update_time;
	}

	/**
	 * Get Approval Link
	 *
	 * @return null|string
	 */
	public function getApprovalLink()
	{
		return $this->getLink('payer-action');
	}

	/**
	 * Get token from Approval Link
	 *
	 * @return null|string
	 */
	public function getToken()
	{
		$parameter_name = "token";
		parse_str(parse_url($this->getApprovalLink(), PHP_URL_QUERY), $query);
		return !isset($query[$parameter_name]) ? null : $query[$parameter_name];
	}

	/**
	 * Creates and processes a payment. In the JSON request body, include a `payment` object with the intent, payer, and transactions. For PayPal payments, include redirect URLs in the `payment` object.
	 *
	 * @param ApiContext $apiContext is the APIContext for this call. It can be used to pass dynamic configuration and credentials.
	 * @param PayPalRestCall $restCall is the Rest Call Service that is used to make rest calls
	 * @return Payment
	 */
	public function create($apiContext = null, $restCall = null)
	{
		$payLoad = $this->toJSON();
		$json = self::executeCall(
			"/v2/checkout/orders",
			"POST",
			$payLoad,
			null,
			$apiContext,
			$restCall
		);
		$this->fromJson($json);
		return $this;
	}

	/**
	 * Shows details for a payment, by ID.
	 *
	 * @param string $paymentId
	 * @param ApiContext $apiContext is the APIContext for this call. It can be used to pass dynamic configuration and credentials.
	 * @param PayPalRestCall $restCall is the Rest Call Service that is used to make rest calls
	 * @return Payment
	 */
	public static function get($paymentId, $apiContext = null, $restCall = null)
	{
		ArgumentValidator::validate($paymentId, 'paymentId');
		$payLoad = "";
		$json = self::executeCall(
			"/v2/checkout/orders/$paymentId",
			"GET",
			$payLoad,
			null,
			$apiContext,
			$restCall
		);
		$ret = new Payment();
		$ret->fromJson($json);
		return $ret;
	}

	/**
	 * Shows details for a payment, by ID.
	 *
	 * @param string $paymentId
	 * @param ApiContext $apiContext is the APIContext for this call. It can be used to pass dynamic configuration and credentials.
	 * @param PayPalRestCall $restCall is the Rest Call Service that is used to make rest calls
	 * @return Payment
	 */
	public function capture($apiContext = null, $restCall = null)
	{
		if ($this->getStatus() === 'APPROVED') {
			$payLoad = "";
			$json = self::executeCall(
				"/v2/checkout/orders/{$this->getId()}/capture",
				"POST",
				$payLoad,
				null,
				$apiContext,
				$restCall
			);
			$ret = new Payment();
			$ret->fromJson($json);
			return $ret;
		}
		return null;
	}

	/**
	 * Partially updates a payment, by ID. You can update the amount, shipping address, invoice ID, and custom data. You cannot use patch after execute has been called.
	 *
	 * @param PatchRequest $patchRequest
	 * @param ApiContext $apiContext is the APIContext for this call. It can be used to pass dynamic configuration and credentials.
	 * @param PayPalRestCall $restCall is the Rest Call Service that is used to make rest calls
	 * @return boolean
	 */
	public function update($patchRequest, $apiContext = null, $restCall = null)
	{
		ArgumentValidator::validate($this->getId(), "Id");
		ArgumentValidator::validate($patchRequest, 'patchRequest');
		$payLoad = $patchRequest->toJSON();
		self::executeCall(
			"/v2/checkout/orders/{$this->getId()}",
			"PATCH",
			$payLoad,
			null,
			$apiContext,
			$restCall
		);
		return true;
	}

	/**
	 * Executes, or completes, a PayPal payment that the payer has approved. You can optionally update selective payment information when you execute a payment.
	 *
	 * @param PaymentExecution $paymentExecution
	 * @param ApiContext $apiContext is the APIContext for this call. It can be used to pass dynamic configuration and credentials.
	 * @param PayPalRestCall $restCall is the Rest Call Service that is used to make rest calls
	 * @return Payment
	 */
	public function execute($paymentExecution, $apiContext = null, $restCall = null)
	{
		ArgumentValidator::validate($this->getId(), "Id");
		ArgumentValidator::validate($paymentExecution, 'paymentExecution');
		$payLoad = $paymentExecution->toJSON();
		$json = self::executeCall(
			"/v1/payments/payment/{$this->getId()}/execute",
			"POST",
			$payLoad,
			null,
			$apiContext,
			$restCall
		);
		$this->fromJson($json);
		return $this;
	}

	/**
	 * List payments that were made to the merchant who issues the request. Payments can be in any status.
	 *
	 * @param array $params
	 * @param ApiContext $apiContext is the APIContext for this call. It can be used to pass dynamic configuration and credentials.
	 * @param PayPalRestCall $restCall is the Rest Call Service that is used to make rest calls
	 * @return PaymentHistory
	 */
	public static function all($params, $apiContext = null, $restCall = null)
	{
		ArgumentValidator::validate($params, 'params');
		$payLoad = "";
		$allowedParams = array(
			'count' => 1,
			'start_id' => 1,
			'start_index' => 1,
			'start_time' => 1,
			'end_time' => 1,
			'payee_id' => 1,
			'sort_by' => 1,
			'sort_order' => 1,
		);
		$json = self::executeCall(
			"/v1/payments/payment?" . http_build_query(array_intersect_key($params, $allowedParams)),
			"GET",
			$payLoad,
			null,
			$apiContext,
			$restCall
		);
		$ret = new PaymentHistory();
		$ret->fromJson($json);
		return $ret;
	}

}
