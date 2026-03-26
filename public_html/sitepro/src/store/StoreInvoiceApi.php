<?php

class StoreInvoiceApi {
	protected $viewPath;

	public function __construct() {
		$this->viewPath = dirname(__FILE__).'/view';
	}

	/**
	 * @param StoreNavigation $request
	 * @return no-return
	 */
	public function process(StoreNavigation $request) {
		$er = @error_reporting();
		@error_reporting($er & ~E_NOTICE);

		$invoiceHash = $request->getArg(1);

		$order = StoreModuleOrder::findByHash($invoiceHash);
		$valid = $order && $order->getInvoiceDocumentNumber();
		if( $valid ) {
			foreach( $order->getItems() as $item ) {
				if( !($item instanceof StoreModuleOrderItem) ) {
					$valid = false;
					break;
				}
			}
		}

		if( !$valid ) {
			@header("Connection: close", true, 404);
			exit;
		}

		if( $order->getLang() ) {
			$request->lang = $order->getLang();
			SiteModule::setLang($request->lang);
		}

		$pdf = new StoreInvoice();

		$pdf->SetCreator("TCPDF");
		$pdf->SetAuthor("");
		$pdf->SetTitle(StoreModule::__('Invoice') . " " . $order->getInvoiceDocumentNumber());
		$pdf->SetSubject(StoreModule::__('Invoice') . " " . $order->getInvoiceDocumentNumber());
		// $invoice->SetKeywords('TCPDF, PDF, example, test, guide');

		ob_start();

		$defaultTax = StoreData::getDefaultTaxSettings();
		$isTaxIncluded = $defaultTax && $defaultTax->enabled && $defaultTax->taxIncluded;

		$taxes = $order->getTaxes();
		if ($isTaxIncluded && $order->getDiscountAmount() && !empty($taxes) && count($taxes)) {
			$price = $order->getPrice();
			foreach ($taxes as $tax) {
				$price -= $tax->amount;
			}
			$subtotal = $price + $order->getDiscountAmount();
		}
		else {
			$subtotal = $order->getPrice() + $order->getDiscountAmount() - $order->getFullTaxAmount() - $order->getShippingAmount();
		}

		$this->renderView($this->viewPath.'/invoice.pdf.php', array(
			"pdf" => $pdf,
			"order" => $order,
			"invoiceTitlePhrase" => StoreData::getInvoiceTitlePhrase(),
			"invoiceTextBeginning" => StoreData::getInvoiceTextBeginning(),
			"invoiceTextEnding" => StoreData::getInvoiceTextEnding(),
			"sellerCompanyInfo" => StoreData::getCompanyInfo(),
			"isLogoImage" => StoreData::getInvoiceLogo() ? true : false,
			"formattedDate" => StoreData::getFormattedDate($order->getDateTime()),
			"subtotal" => $subtotal
		));
		if (function_exists('ini_set')) @ini_set("display_errors", false);

		$html = ob_get_clean();

		$pdf->AddPage();

		$logoImage = StoreData::getInvoiceLogo();
		if ($logoImage) {
			$logoImage = dirname(dirname(__DIR__)) . '/' . $logoImage;
			$align = StoreData::getLogoAlign();
			$align = $align === 'left' ? 'L' : ($align === 'right' ? 'R' : 'C');

			list(, $image_h) = getimagesize($logoImage);
			$height = StoreData::getLogoHeight();
			$height = min($image_h, $height);

			$pdf->Image($logoImage, '', '', '', $pdf->pixelsToUnits($height), '', '', 'N', false, 300, $align, false, false, 0, 'CM');
			$pdf->SetY($pdf->GetY() + $pdf->pixelsToUnits(20));
		}

		$pdf->writeHTML($html);

		$signImage = StoreData::getSignImage();
		if ($signImage) {
			$signImage = dirname(dirname(__DIR__)) . '/' . $signImage;
			$align = StoreData::getSignImageAlign();
			$align = $align === 'left' ? 'L' : ($align === 'right' ? 'R' : 'C');

			list(, $image_h) = getimagesize($signImage);
			$height = StoreData::getSignImageHeight();
			$height = min($image_h, $height);

			$pdf->Image($signImage, '', '', '', $pdf->pixelsToUnits($height), '', '', '', false, 300, $align, false, false, 0, 'CM');
		}

		$pdf->lastPage();
		$pdf->endPage();
		$pdf->Close();

		$invoiceFileNumber = (string)$order->getInvoiceDocumentNumber();
		if( extension_loaded("intl") && class_exists("Transliterator") )
			$invoiceFileNumber = Transliterator::create('Any-Latin;Latin-ASCII')->transliterate($invoiceFileNumber);
		$invoiceFileNumber = preg_replace("#[^a-z0-9_\\-]#isu", "_", mb_strtolower($invoiceFileNumber, "utf-8"));

		@error_reporting($er);

		StoreModule::respondWithPDF($pdf, "invoice_" . $invoiceFileNumber . ".pdf"); // ends with exit()
	}

	/**
	 * Render template.
	 * @param string $templatePath path to template file.
	 * @param array $vars associative array with template variable values.
	 */
	protected function renderView($templatePath, $vars) {
		extract($vars);
		require $templatePath;
	}
}
